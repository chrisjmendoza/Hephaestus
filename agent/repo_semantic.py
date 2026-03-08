"""Semantic repository indexing and search for Hephaestus."""

from __future__ import annotations

import json
import math
from pathlib import Path

from sentence_transformers import SentenceTransformer


class RepoSemanticIndex:
    """Builds and queries semantic embeddings for repository Python files."""

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
        """Build semantic embeddings for indexed Python files and persist them."""
        repo_root = Path(repo_path).resolve()
        repo_index = self._load_repo_index()
        python_files = repo_index.get("python_files", [])

        texts: list[str] = []
        paths: list[str] = []
        for relative_path in python_files:
            file_path = repo_root / relative_path
            if not file_path.exists():
                continue
            try:
                content = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            texts.append(content)
            paths.append(relative_path)

        model = self._get_model()
        vectors = model.encode(texts, convert_to_numpy=True) if texts else []

        payload = {
            "files": [
                {"path": path, "embedding": vector.tolist()}
                for path, vector in zip(paths, vectors)
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
