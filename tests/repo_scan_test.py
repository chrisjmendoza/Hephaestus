"""Smoke-style repository scan test for Hephaestus v0.2."""

from __future__ import annotations

import json
from pathlib import Path
import sys


def main() -> None:
    """Scan the current repository and validate index output."""
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from agent.agent import HephaestusAgent

    index_path = project_root / "memory" / "repo_index.json"
    if index_path.exists():
        index_path.unlink()

    agent = HephaestusAgent(memory_root=str(project_root / "memory"))
    index = agent.scan_repo(str(project_root))

    assert index_path.exists(), "Repository index file was not created"

    file_index = json.loads(index_path.read_text(encoding="utf-8"))
    assert len(file_index.get("python_files", [])) > 0, "No Python files detected"
    assert len(index.get("python_files", [])) > 0, "Scan result has no Python files"

    print("PASS")
    print("Repository scan test passed")


if __name__ == "__main__":
    main()
