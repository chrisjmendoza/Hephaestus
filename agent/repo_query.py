"""Repository index query utilities for Hephaestus."""

from __future__ import annotations

import json
from pathlib import Path


class RepoQuery:
    """Loads and queries structured repository index data."""

    def __init__(self, index_path: str | Path = "memory/repo_index.json") -> None:
        """Initialize with the location of the repository index file."""
        self.index_path = Path(index_path)
        self._index: dict | None = None

    def load_index(self) -> dict:
        """Load and return repository index data from disk."""
        if not self.index_path.exists():
            raise FileNotFoundError(
                f"Repository index not found at {self.index_path}. Run scan first."
            )
        self._index = json.loads(self.index_path.read_text(encoding="utf-8"))
        return self._index

    def get_python_files(self) -> list[str]:
        """Return detected Python files from the repository index."""
        index = self._index or self.load_index()
        return index.get("python_files", [])

    def get_test_files(self) -> list[str]:
        """Return detected test files from the repository index."""
        index = self._index or self.load_index()
        return index.get("test_files", [])

    def get_entrypoints(self) -> list[str]:
        """Return detected entrypoint files from the repository index."""
        index = self._index or self.load_index()
        return index.get("entrypoints", [])

    def get_config_files(self) -> list[str]:
        """Return detected config files from the repository index."""
        index = self._index or self.load_index()
        return index.get("config_files", [])

    def get_directory_summary(self) -> dict[str, int]:
        """Return a file-count summary grouped by top-level directory."""
        index = self._index or self.load_index()
        summary: dict[str, int] = {}

        for relative_path in index.get("files", []):
            parts = Path(relative_path).parts
            if len(parts) > 1:
                key = parts[0]
            else:
                key = "."
            summary[key] = summary.get(key, 0) + 1

        return dict(sorted(summary.items()))
