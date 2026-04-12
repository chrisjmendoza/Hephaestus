"""Tests for --dry-run mode in run_task() and execute_step()."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from agent.agent import HephaestusAgent


def _make_agent() -> HephaestusAgent:
    agent = HephaestusAgent(log_path="logs/test_dry_run.log")
    return agent


def _mock_plan(steps: list[str]):
    """Return a patcher that makes generate_task_plan return the given steps."""
    return patch.object(HephaestusAgent, "generate_task_plan", return_value=steps)


# ---------------------------------------------------------------------------
# execute_step dry-run
# ---------------------------------------------------------------------------

def test_dry_run_skips_patch_step():
    agent = _make_agent()
    result = agent.execute_step("implement changes to agent.py", dry_run=True)
    assert "[dry-run]" in result
    assert "patch" in result.lower() or "would" in result.lower()
    print("PASS: dry-run skips patch step")


def test_dry_run_skips_test_step():
    agent = _make_agent()
    result = agent.execute_step("validate and run tests", dry_run=True)
    assert "[dry-run]" in result
    print("PASS: dry-run skips test step")


def test_dry_run_skips_commit_step():
    agent = _make_agent()
    result = agent.execute_step("commit the changes", dry_run=True)
    assert "[dry-run]" in result
    print("PASS: dry-run skips commit step")


def test_dry_run_allows_search_step():
    """Search/analyze steps still execute in dry-run — they are read-only."""
    agent = _make_agent()
    with patch.object(agent, "semantic_search", return_value=["agent/agent.py"]):
        result = agent.execute_step("analyze repository structure", dry_run=True)
    assert "[dry-run]" not in result
    assert "agent/agent.py" in result
    print("PASS: dry-run allows search step")


def test_dry_run_allows_read_step():
    """Read steps still execute in dry-run — they are read-only."""
    agent = _make_agent()
    result = agent.execute_step("read the README or inspect the codebase", dry_run=True)
    # Should attempt to read but not be blocked by dry-run
    assert "[dry-run]" not in result
    print("PASS: dry-run allows read step")


# ---------------------------------------------------------------------------
# run_task dry-run
# ---------------------------------------------------------------------------

def test_run_task_dry_run_output_contains_dry_run_markers():
    agent = _make_agent()
    with _mock_plan(["implement changes to main.py", "commit the changes"]):
        output = agent.run_task("Fix the bug", dry_run=True)
    assert "[dry-run]" in output
    print("PASS: run_task dry-run output contains [dry-run] markers")


def test_run_task_dry_run_logs_dry_run_enabled():
    log_path = project_root / "logs" / "test_dry_run_log_check.log"
    if log_path.exists():
        log_path.unlink()

    agent = HephaestusAgent(log_path=str(log_path))
    with _mock_plan(["analyze repository"]):
        with patch.object(agent, "semantic_search", return_value=[]):
            agent.run_task("Some task", dry_run=True)

    log_text = log_path.read_text(encoding="utf-8")
    assert "DRY_RUN_ENABLED" in log_text
    print("PASS: run_task dry-run logs DRY_RUN_ENABLED event")


def test_run_task_no_dry_run_does_not_log_dry_run_enabled():
    log_path = project_root / "logs" / "test_no_dry_run_log_check.log"
    if log_path.exists():
        log_path.unlink()

    agent = HephaestusAgent(log_path=str(log_path))
    with _mock_plan(["analyze repository"]):
        with patch.object(agent, "semantic_search", return_value=[]):
            agent.run_task("Some task", dry_run=False)

    log_text = log_path.read_text(encoding="utf-8")
    assert "DRY_RUN_ENABLED" not in log_text
    print("PASS: normal run_task does not log DRY_RUN_ENABLED")


# ---------------------------------------------------------------------------
# CLI dry-run
# ---------------------------------------------------------------------------

def test_cli_dry_run_flag_parsed(monkeypatch=None):
    """Verify main() passes dry_run=True to run_task when --dry-run is present."""
    captured: dict = {}

    def mock_run_task(self, task: str, dry_run: bool = False) -> str:
        captured["dry_run"] = dry_run
        captured["task"] = task
        return "done"

    with patch.object(HephaestusAgent, "run_task", mock_run_task):
        with patch("sys.argv", ["main.py", "Fix the bug", "--dry-run"]):
            import importlib
            import main as main_module  # noqa: PLC0415
            importlib.reload(main_module)
            main_module.main()

    assert captured.get("dry_run") is True
    assert captured.get("task") == "Fix the bug"
    print("PASS: CLI --dry-run flag sets dry_run=True in run_task call")


def test_cli_no_dry_run_flag_defaults_false():
    """Verify main() passes dry_run=False when --dry-run is absent."""
    captured: dict = {}

    def mock_run_task(self, task: str, dry_run: bool = False) -> str:
        captured["dry_run"] = dry_run
        return "done"

    with patch.object(HephaestusAgent, "run_task", mock_run_task):
        with patch("sys.argv", ["main.py", "Fix the bug"]):
            import importlib
            import main as main_module  # noqa: PLC0415
            importlib.reload(main_module)
            main_module.main()

    assert captured.get("dry_run") is False
    print("PASS: CLI without --dry-run defaults to dry_run=False")


if __name__ == "__main__":
    test_dry_run_skips_patch_step()
    test_dry_run_skips_test_step()
    test_dry_run_skips_commit_step()
    test_dry_run_allows_search_step()
    test_dry_run_allows_read_step()
    test_run_task_dry_run_output_contains_dry_run_markers()
    test_run_task_dry_run_logs_dry_run_enabled()
    test_run_task_no_dry_run_does_not_log_dry_run_enabled()
    test_cli_dry_run_flag_parsed()
    test_cli_no_dry_run_flag_defaults_false()
    print("\n=== dry_run tests PASSED ===")
