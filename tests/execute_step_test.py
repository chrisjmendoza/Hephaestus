"""Tests for HephaestusAgent.execute_step() keyword dispatcher."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch


def main() -> None:
    """Test execute_step dispatch for each keyword category."""
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from agent.agent import HephaestusAgent

    # ------------------------------------------------------------------
    # Helpers: create a minimal agent with a temp log file
    # ------------------------------------------------------------------
    def make_agent(tmpdir: str) -> HephaestusAgent:
        log = Path(tmpdir) / "test.log"
        return HephaestusAgent(log_path=str(log))

    # ------------------------------------------------------------------
    # 1. Search keywords → semantic_search is called
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = make_agent(tmpdir)
        with patch.object(agent, "semantic_search", return_value=["agent/tools.py"]) as mock_search:
            result = agent.execute_step("Analyze task requirements for: refactor tools")
            mock_search.assert_called_once()
            assert "agent/tools.py" in result, f"Expected file in output, got: {result}"
        print("PASS: search dispatch")

    # ------------------------------------------------------------------
    # 2. Search with no results
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = make_agent(tmpdir)
        with patch.object(agent, "semantic_search", return_value=[]):
            result = agent.execute_step("Find relevant files for: empty query")
            assert "No matches" in result, f"Expected no-match message, got: {result}"
        print("PASS: search no results")

    # ------------------------------------------------------------------
    # 3. Read keyword with a valid file path token
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = make_agent(tmpdir)
        # Create a real .py file in tmpdir
        sample = Path(tmpdir) / "sample.py"
        sample.write_text("x = 1\n", encoding="utf-8")
        result = agent.execute_step(f"Read {sample} to understand context", repo_path=tmpdir)
        assert "sample.py" in result and "chars" in result, f"Unexpected: {result}"
        print("PASS: read dispatch")

    # ------------------------------------------------------------------
    # 4. Read keyword with no recognisable file → graceful message
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = make_agent(tmpdir)
        result = agent.execute_step("Inspect the codebase structure")
        assert "No readable file" in result, f"Expected graceful message, got: {result}"
        print("PASS: read no file found")

    # ------------------------------------------------------------------
    # 5. Implement keyword → dry-run message (no file mutation)
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = make_agent(tmpdir)
        result = agent.execute_step("Implement the changes in tools.py")
        assert "dry-run" in result, f"Expected dry-run message, got: {result}"
        print("PASS: implement dry-run")

    # ------------------------------------------------------------------
    # 6. Test keyword → run_tests is called
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = make_agent(tmpdir)
        mock_result = MagicMock()
        mock_result.passed = True
        mock_result.summary = "3 passed"
        with patch.object(agent, "run_tests", return_value=mock_result) as mock_tests:
            result = agent.execute_step("Run tests to validate changes")
            mock_tests.assert_called_once()
            assert "passed" in result, f"Expected test summary, got: {result}"
        print("PASS: test dispatch")

    # ------------------------------------------------------------------
    # 7. Commit keyword → dry-run message (no actual commit)
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = make_agent(tmpdir)
        result = agent.execute_step("Commit the implemented changes")
        assert "dry-run" in result, f"Expected dry-run message, got: {result}"
        print("PASS: commit dry-run")

    # ------------------------------------------------------------------
    # 8. Unrecognised step → fallback echo
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = make_agent(tmpdir)
        result = agent.execute_step("Define minimal code changes aligned with current architecture")
        assert "step executed" in result, f"Expected echo fallback, got: {result}"
        print("PASS: fallback echo")

    # ------------------------------------------------------------------
    # 9. Lifecycle events are logged for every step
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "test.log"
        agent = HephaestusAgent(log_path=str(log_path))
        with patch.object(agent, "semantic_search", return_value=["main.py"]):
            agent.execute_step("Review relevant files")
        log = log_path.read_text(encoding="utf-8")
        assert "STEP_START" in log, "Missing STEP_START in log"
        assert "STEP_COMPLETE" in log, "Missing STEP_COMPLETE in log"
        print("PASS: lifecycle logging")

    print("\n=== execute_step tests PASSED ===")


if __name__ == "__main__":
    main()
