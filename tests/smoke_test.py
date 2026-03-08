"""Assertion-based smoke test for Hephaestus lifecycle events."""

from __future__ import annotations

from pathlib import Path
import sys


def main() -> None:
    """Run a task and assert that required lifecycle events were logged."""
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from agent.agent import HephaestusAgent

    test_task = "Analyze repository structure"
    log_path = project_root / "logs" / "hephaestus.log"
    if log_path.exists():
        log_path.unlink()

    agent = HephaestusAgent(log_path=str(log_path))
    result = agent.run_task(test_task)

    log_contents = log_path.read_text(encoding="utf-8")
    required_events = [
        "TASK_RECEIVED",
        "PLAN_CREATED",
        "STEP_START",
        "STEP_COMPLETE",
        "TASK_COMPLETE",
    ]
    for event in required_events:
        assert event in log_contents, f"Missing lifecycle event in logs: {event}"

    print("=== Hephaestus Smoke Test ===")
    print(f"Task: {test_task}")
    print(result)
    print("PASS")
    print("Smoke test passed")
    print("Lifecycle events verified")


if __name__ == "__main__":
    main()
