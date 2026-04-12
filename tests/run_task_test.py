"""Tests for HephaestusAgent.run_task() — repo_path propagation and generate_report."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, call, patch


def main() -> None:
    """Test run_task repo_path propagation and report generation."""
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from agent.agent import HephaestusAgent

    def make_agent(tmpdir: str) -> HephaestusAgent:
        log = Path(tmpdir) / "test.log"
        return HephaestusAgent(log_path=str(log))

    # ------------------------------------------------------------------
    # 1. run_task passes repo_path to every execute_step call (P1.2)
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = make_agent(tmpdir)
        plan = ["Analyze the codebase", "Implement the fix", "Run tests"]
        with patch.object(agent, "generate_task_plan", return_value=plan):
            with patch.object(agent, "generate_report"):
                with patch.object(agent, "execute_step", return_value="step: result") as mock_step:
                    agent.run_task("fix the bug", repo_path="/my/repo")
                    for c in mock_step.call_args_list:
                        assert c.kwargs.get("repo_path") == "/my/repo" or c.args[1] == "/my/repo", \
                            f"execute_step not called with repo_path='/my/repo': {c}"
        print("PASS: run_task propagates repo_path to execute_step")

    # ------------------------------------------------------------------
    # 2. run_task passes repo_path to generate_task_plan (P1.2)
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = make_agent(tmpdir)
        with patch.object(agent, "generate_task_plan", return_value=["step"]) as mock_plan:
            with patch.object(agent, "generate_report"):
                with patch.object(agent, "execute_step", return_value="step: ok"):
                    agent.run_task("do something", repo_path="/target/repo")
                    mock_plan.assert_called_once_with("do something", repo_path="/target/repo")
        print("PASS: run_task propagates repo_path to generate_task_plan")

    # ------------------------------------------------------------------
    # 3. run_task calls generate_report after execution (P2.2)
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = make_agent(tmpdir)
        plan = ["Do a thing"]
        with patch.object(agent, "generate_task_plan", return_value=plan):
            with patch.object(agent, "execute_step", return_value="Do a thing: result"):
                with patch.object(agent, "generate_report") as mock_report:
                    agent.run_task("do a thing")
                    mock_report.assert_called_once()
                    call_kwargs = mock_report.call_args
                    assert call_kwargs[0][0] == "do a thing", \
                        f"generate_report called with wrong task: {call_kwargs}"
        print("PASS: run_task calls generate_report")

    # ------------------------------------------------------------------
    # 4. run_task prints step progress lines (P4.1)
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = make_agent(tmpdir)
        plan = ["First step", "Second step"]
        printed: list[str] = []
        with patch.object(agent, "generate_task_plan", return_value=plan):
            with patch.object(agent, "generate_report"):
                with patch.object(agent, "execute_step", return_value="step: ok"):
                    with patch("builtins.print", side_effect=printed.append):
                        agent.run_task("multi step task")
        assert any("[step 1/2]" in str(p) for p in printed), \
            f"Expected '[step 1/2]' progress output, got: {printed}"
        assert any("[step 2/2]" in str(p) for p in printed), \
            f"Expected '[step 2/2]' progress output, got: {printed}"
        print("PASS: run_task prints step N/M progress")

    # ------------------------------------------------------------------
    # 5. run_task default repo_path is "." (backward compatibility)
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = make_agent(tmpdir)
        with patch.object(agent, "generate_task_plan", return_value=["step"]) as mock_plan:
            with patch.object(agent, "generate_report"):
                with patch.object(agent, "execute_step", return_value="step: ok") as mock_step:
                    agent.run_task("no repo")
                    mock_plan.assert_called_once_with("no repo", repo_path=".")
                    for c in mock_step.call_args_list:
                        rp = c.kwargs.get("repo_path") or (c.args[1] if len(c.args) > 1 else ".")
                        assert rp == ".", f"expected repo_path='.', got: {rp}"
        print("PASS: run_task defaults repo_path to '.'")

    print("\n=== run_task tests PASSED ===")


if __name__ == "__main__":
    main()
