"""Smoke test for Hephaestus v0.1.1 operational loop."""

from __future__ import annotations

from pathlib import Path
import sys


def main() -> None:
    """Run a simple task through the agent and print output."""
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from agent.agent import HephaestusAgent

    test_task = "Analyze repository structure"
    agent = HephaestusAgent()
    result = agent.run_task(test_task)

    print("=== Hephaestus Smoke Test ===")
    print(f"Task: {test_task}")
    print(result)


if __name__ == "__main__":
    main()
