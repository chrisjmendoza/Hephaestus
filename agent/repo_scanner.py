"""Repository scanning utilities for Hephaestus."""

from __future__ import annotations

import json
from pathlib import Path


class RepoScanner:
    """Scans a repository and builds a lightweight structural index."""

    _EXCLUDED_DIRS = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        "node_modules",
    }

    _CONFIG_NAMES = {
        "requirements.txt",
        "pyproject.toml",
        "setup.py",
        "dockerfile",
        ".env",
        "package.json",
    }

    _ENTRYPOINT_NAMES = {
        "main.py",
        "app.py",
        "server.py",
        "run.py",
        "__main__.py",
    }

    def __init__(self, index_path: str | Path = "memory/repo_index.json") -> None:
        """Initialize scanner with an output location for the generated index."""
        self.index_path = Path(index_path)

    def scan_repository(self, repo_path: str) -> dict:
        """Scan a repository, save its index to disk, and return the index."""
        root = Path(repo_path).resolve()

        python_files: list[str] = []
        test_files: list[str] = []
        entrypoints: list[str] = []
        config_files: list[str] = []
        directories: list[str] = []
        all_files: list[str] = []

        for path in root.rglob("*"):
            if any(part in self._EXCLUDED_DIRS for part in path.parts):
                continue

            if path.is_dir():
                directories.append(str(path.relative_to(root).as_posix()))
                continue

            relative_path = str(path.relative_to(root).as_posix())
            all_files.append(relative_path)

            name_lower = path.name.lower()
            if path.suffix == ".py":
                python_files.append(relative_path)

            if name_lower.startswith("test_") and path.suffix == ".py":
                test_files.append(relative_path)
            elif "tests" in Path(relative_path).parts:
                test_files.append(relative_path)

            if path.name in self._ENTRYPOINT_NAMES:
                entrypoints.append(relative_path)

            if name_lower in self._CONFIG_NAMES:
                config_files.append(relative_path)

        index = {
            "total_files": len(all_files),
            "files": sorted(set(all_files)),
            "python_files": sorted(set(python_files)),
            "test_files": sorted(set(test_files)),
            "entrypoints": sorted(set(entrypoints)),
            "config_files": sorted(set(config_files)),
            "directories": sorted(set(directories)),
        }

        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
        return index


def scan_repository(repo_path: str) -> dict:
    """Convenience function that scans and indexes a repository."""
    return RepoScanner().scan_repository(repo_path)
