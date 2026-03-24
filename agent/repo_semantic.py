"""Semantic repository indexing and search for Hephaestus."""

from __future__ import annotations

import json
import math
from pathlib import Path

from sentence_transformers import SentenceTransformer


class RepoSemanticIndex:
    """Builds and queries semantic embeddings for repository source files."""

    def __init__(
        self,
        index_path: str | Path = "memory/repo_index.json",
        embeddings_path: str | Path = "memory/repo_embeddings.json",
        model_name: str = "all-MiniLM-L6-v2",
    ) -> None:
        """Initialize paths and embedding model configuration."""
        self.index_path = Path(index_path)
        self.embeddings_path = Path(embeddings_path)
        self.model_name = model_name
        self._model: SentenceTransformer | None = None

    def _get_model(self) -> SentenceTransformer:
        """Load and cache the sentence transformer model."""
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def _load_repo_index(self) -> dict:
        """Load repository index data produced by repository scanner."""
        if not self.index_path.exists():
            raise FileNotFoundError(
                f"Repository index not found at {self.index_path}. Run scan first."
            )
        return json.loads(self.index_path.read_text(encoding="utf-8"))

    def build_index(self, repo_path: str) -> dict:
        """Build semantic embeddings for indexed source files and persist them.

        Files whose mtime matches the stored cache are skipped — only new or
        modified files are re-embedded, and removed files are evicted.
        """
        repo_root = Path(repo_path).resolve()
        repo_index = self._load_repo_index()

        source_files = (
            repo_index.get("python_files", [])
            + repo_index.get("kotlin_files", [])
            + repo_index.get("java_files", [])
            + repo_index.get("js_files", [])
            + repo_index.get("csharp_files", [])
            + repo_index.get("cpp_files", [])
        )

        xml_candidates = repo_index.get("xml_files", [])
        xml_files: list[str] = []
        for relative_path in xml_candidates:
            file_path = repo_root / relative_path
            if not file_path.exists():
                continue
            try:
                if file_path.stat().st_size < 10_000:
                    xml_files.append(relative_path)
            except OSError:
                continue

        index_files = sorted(set(source_files + xml_files))

        # Load existing cache keyed by relative path
        cached: dict[str, dict] = {}
        if self.embeddings_path.exists():
            try:
                existing = json.loads(self.embeddings_path.read_text(encoding="utf-8"))
                for item in existing.get("files", []):
                    if item.get("path"):
                        cached[item["path"]] = item
            except (json.JSONDecodeError, OSError):
                cached = {}

        stale_paths: list[str] = []
        stale_texts: list[str] = []

        for relative_path in index_files:
            file_path = repo_root / relative_path
            if not file_path.exists():
                continue
            try:
                mtime = file_path.stat().st_mtime
                content = file_path.read_text(encoding="utf-8")[:1000]
            except (OSError, UnicodeDecodeError):
                continue

            prior = cached.get(relative_path)
            if prior and prior.get("mtime") == mtime:
                # File unchanged — keep cached embedding as-is
                continue

            stale_paths.append(relative_path)
            stale_texts.append(content)

        # Re-embed only stale files
        if stale_texts:
            model = self._get_model()
            new_vectors = model.encode(stale_texts, convert_to_numpy=True)
            for relative_path, vector in zip(stale_paths, new_vectors):
                file_path = repo_root / relative_path
                try:
                    mtime = file_path.stat().st_mtime
                except OSError:
                    mtime = 0.0
                cached[relative_path] = {
                    "path": relative_path,
                    "mtime": mtime,
                    "embedding": vector.tolist(),
                }

        # Evict files no longer in the index
        valid_set = set(index_files)
        payload = {
            "files": [
                item for path, item in cached.items() if path in valid_set
            ]
        }

        self.embeddings_path.parent.mkdir(parents=True, exist_ok=True)
        self.embeddings_path.write_text(json.dumps(payload), encoding="utf-8")
        return payload

    def _load_embeddings(self) -> dict:
        """Load semantic embeddings from local storage."""
        if not self.embeddings_path.exists():
            raise FileNotFoundError(
                f"Semantic embeddings not found at {self.embeddings_path}. Build index first."
            )
        return json.loads(self.embeddings_path.read_text(encoding="utf-8"))

    @staticmethod
    def _cosine_similarity(vector_a: list[float], vector_b: list[float]) -> float:
        """Compute cosine similarity between two embedding vectors."""
        dot_product = sum(a * b for a, b in zip(vector_a, vector_b))
        magnitude_a = math.sqrt(sum(a * a for a in vector_a))
        magnitude_b = math.sqrt(sum(b * b for b in vector_b))
        if magnitude_a == 0 or magnitude_b == 0:
            return 0.0
        return dot_product / (magnitude_a * magnitude_b)

    def search(self, query: str, top_k: int = 5) -> list[str]:
        """Run semantic similarity search and return top matching file paths."""
        model = self._get_model()
        query_vector = model.encode(query, convert_to_numpy=True).tolist()

        payload = self._load_embeddings()
        scored: list[tuple[str, float]] = []
        for item in payload.get("files", []):
            path = item.get("path")
            embedding = item.get("embedding", [])
            if not path or not embedding:
                continue
            score = self._cosine_similarity(query_vector, embedding)
            scored.append((path, score))

        scored.sort(key=lambda value: value[1], reverse=True)
        return [path for path, _ in scored[:top_k]]
