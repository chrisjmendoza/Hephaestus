"""Smoke-style task reasoning test for Hephaestus v0.5."""

from __future__ import annotations

import json
from pathlib import Path
import sys


def main() -> None:
    """Generate a task plan and verify plan persistence."""
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from agent.agent import HephaestusAgent

    task_plan_path = project_root / "memory" / "task_plan.json"
    if task_plan_path.exists():
        task_plan_path.unlink()

    agent = HephaestusAgent()
    plan = agent.generate_task_plan("analyze repository structure", repo_path=str(project_root))

    assert len(plan) > 0, "Generated plan is empty"
    assert task_plan_path.exists(), "task_plan.json was not created"

    payload = json.loads(task_plan_path.read_text(encoding="utf-8"))
    assert len(payload.get("plan", [])) > 0, "Persisted plan is empty"

    print("PASS")
    print("Task reasoner test passed")


if __name__ == "__main__":
    main()
