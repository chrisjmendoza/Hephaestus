"""Smoke-style repository query test for Hephaestus v0.3."""

from __future__ import annotations

from pathlib import Path
import sys


def main() -> None:
    """Ensure repository index can be loaded and queried for Python files."""
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from agent.agent import HephaestusAgent

    index_path = project_root / "memory" / "repo_index.json"
    agent = HephaestusAgent()

    if not index_path.exists():
        agent.scan_repo(str(project_root))

    assert index_path.exists(), "Repository index file does not exist"

    python_files = agent.query_repo("python")
    assert len(python_files) > 0, "No Python files returned by repository query"

    print("PASS")
    print("Repository query test passed")


if __name__ == "__main__":
    main()
