"""Tests for mtime-based embedding cache in RepoSemanticIndex."""

from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path


def _write_repo_index(index_path: Path, python_files: list[str]) -> None:
    """Write a minimal repo index pointing at the given files."""
    payload = {
        "total_files": len(python_files),
        "python_files": python_files,
        "kotlin_files": [],
        "java_files": [],
        "js_files": [],
        "csharp_files": [],
        "cpp_files": [],
        "xml_files": [],
        "test_files": [],
        "entrypoints": [],
        "config_files": [],
        "directories": [],
        "language_counts": {"python": len(python_files)},
    }
    index_path.write_text(json.dumps(payload), encoding="utf-8")


def main() -> None:
    """Verify that unchanged files are not re-embedded and changed files are."""
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from agent.repo_semantic import RepoSemanticIndex

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        index_path = repo_root / "repo_index.json"
        embeddings_path = repo_root / "repo_embeddings.json"

        # Create two source files
        file_a = repo_root / "module_a.py"
        file_b = repo_root / "module_b.py"
        file_a.write_text("def foo(): pass\n", encoding="utf-8")
        file_b.write_text("def bar(): pass\n", encoding="utf-8")

        _write_repo_index(index_path, ["module_a.py", "module_b.py"])

        semantic = RepoSemanticIndex(
            index_path=index_path,
            embeddings_path=embeddings_path,
        )

        # --- First build: both files embedded ---
        payload1 = semantic.build_index(str(repo_root))
        paths1 = {item["path"] for item in payload1["files"]}
        assert "module_a.py" in paths1, "module_a.py should be in first build"
        assert "module_b.py" in paths1, "module_b.py should be in first build"

        # Record mtime-stamped embeddings for both files
        emb1 = {item["path"]: item["embedding"] for item in payload1["files"]}

        # --- Second build: no changes, embeddings must be identical (no re-encode) ---
        payload2 = semantic.build_index(str(repo_root))
        emb2 = {item["path"]: item["embedding"] for item in payload2["files"]}
        assert emb1["module_a.py"] == emb2["module_a.py"], (
            "Unchanged file should reuse cached embedding"
        )
        assert emb1["module_b.py"] == emb2["module_b.py"], (
            "Unchanged file should reuse cached embedding"
        )

        # --- Modify file_a and wait to ensure mtime advances ---
        time.sleep(0.05)
        file_a.write_text("def foo(): return 42\n", encoding="utf-8")

        payload3 = semantic.build_index(str(repo_root))
        emb3 = {item["path"]: item["embedding"] for item in payload3["files"]}

        assert emb3["module_a.py"] != emb1["module_a.py"], (
            "Modified file should produce a new embedding"
        )
        assert emb3["module_b.py"] == emb2["module_b.py"], (
            "Unmodified file should still use cached embedding"
        )

        # --- Eviction: remove module_b from index, rebuild ---
        _write_repo_index(index_path, ["module_a.py"])
        payload4 = semantic.build_index(str(repo_root))
        paths4 = {item["path"] for item in payload4["files"]}
        assert "module_b.py" not in paths4, (
            "Removed file should be evicted from the cache"
        )
        assert "module_a.py" in paths4

        # --- mtime field is persisted ---
        raw = json.loads(embeddings_path.read_text(encoding="utf-8"))
        for item in raw["files"]:
            assert "mtime" in item, f"mtime missing for {item['path']}"

    print("PASS")
    print("Embedding cache test passed")


if __name__ == "__main__":
    main()
