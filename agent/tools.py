"""Utility tool functions used by the Hephaestus agent."""

from __future__ import annotations

import subprocess
from pathlib import Path


def read_file(path: str) -> str:
    """Read and return file content."""
    return Path(path).read_text(encoding="utf-8")


def write_file(path: str, content: str) -> str:
    """Write content to a file and return the written path."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return str(target)


def search_repo(query: str, top_k: int = 5) -> list[str]:
    """Search the repository using semantic similarity for the given query."""
    from .repo_semantic import RepoSemanticIndex  # lazy to avoid heavy startup cost
    index = RepoSemanticIndex()
    return index.search(query, top_k=top_k)


def run_command(cmd: str) -> str:
    """Run a shell command and return combined output."""
    completed = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    return (completed.stdout + completed.stderr).strip()


def git_diff() -> str:
    """Return the current git diff output."""
    return run_command("git diff")


def git_commit(message: str) -> str:
    """Create a git commit with the provided message."""
    return run_command(f'git commit -m "{message}"')
