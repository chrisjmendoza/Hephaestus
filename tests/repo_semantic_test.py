"""Smoke-style semantic repository search test for Hephaestus v0.4."""

from __future__ import annotations

from pathlib import Path
import sys


def main() -> None:
    """Build semantic index and verify semantic search returns matches."""
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from agent.agent import HephaestusAgent

    index_path = project_root / "memory" / "repo_index.json"
    agent = HephaestusAgent()

    if not index_path.exists():
        agent.scan_repo(str(project_root))

    results = agent.semantic_search("repository scanner", repo_path=str(project_root))
    assert len(results) > 0, "Semantic search returned no results"

    print("PASS")
    print("Repository semantic search test passed")


if __name__ == "__main__":
    main()
