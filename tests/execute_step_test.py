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
    # 5. Implement keyword with no target file → [skip] message
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = make_agent(tmpdir)
        # tools.py does not exist in tmpdir
        result = agent.execute_step("Implement the changes in tools.py", repo_path=tmpdir)
        assert "skip" in result.lower(), f"Expected skip message, got: {result}"
        print("PASS: implement no target file")

    # ------------------------------------------------------------------
    # 5b. Implement keyword with an existing file → patch applied
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = make_agent(tmpdir)
        sample = Path(tmpdir) / "sample.py"
        sample.write_text("x = 1\n", encoding="utf-8")
        mock_patch = MagicMock()
        mock_patch.diff = "--- a/sample.py\n+++ b/sample.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n"
        mock_patch.applied = True
        with patch.object(agent.task_reasoner, "generate_patch", return_value="x = 2\n") as mock_gen:
            with patch.object(agent, "apply_patch", return_value=mock_patch) as mock_apply:
                result = agent.execute_step(f"Implement the changes in sample.py", repo_path=tmpdir)
                mock_gen.assert_called_once()
                mock_apply.assert_called_once()
                assert "Patched" in result, f"Expected Patched in output, got: {result}"
        print("PASS: implement real patch")

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
    # 7. Commit keyword with no git repo → graceful [skip]
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = make_agent(tmpdir)
        result = agent.execute_step("Commit the implemented changes", repo_path=tmpdir)
        assert "skip" in result.lower() or "nothing to commit" in result.lower(), \
            f"Expected skip or nothing-to-commit message, got: {result}"
        print("PASS: commit no git repo")

    # ------------------------------------------------------------------
    # 7b. Commit keyword with staged files → git_commit_patch called
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = make_agent(tmpdir)
        mock_status = MagicMock()
        mock_status.staged_files = ["agent/tools.py"]
        mock_status.unstaged_files = []
        mock_commit_result = MagicMock()
        mock_commit_result.files_committed = ["agent/tools.py"]
        mock_commit_result.commit_sha = "abc1234"
        with patch.object(agent, "git_status", return_value=mock_status):
            with patch.object(agent, "git_commit_patch", return_value=mock_commit_result) as mock_commit:
                result = agent.execute_step("Commit the implemented changes")
                mock_commit.assert_called_once()
                assert "Committed" in result, f"Expected Committed in output, got: {result}"
        print("PASS: commit real commit")

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

    # ------------------------------------------------------------------
    # 10. Implement step with no path token uses semantic_search (P1.1)
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = make_agent(tmpdir)
        sample = Path(tmpdir) / "sample.py"
        sample.write_text("x = 1\n", encoding="utf-8")
        mock_patch = MagicMock()
        mock_patch.diff = "--- a/sample.py\n+++ b/sample.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n"
        mock_patch.applied = True
        with patch.object(agent, "semantic_search", return_value=["sample.py"]) as mock_sem:
            with patch.object(agent.task_reasoner, "generate_patch", return_value="x = 2\n"):
                with patch.object(agent, "apply_patch", return_value=mock_patch):
                    result = agent.execute_step(
                        "Implement the task reasoner edge case handling",
                        repo_path=tmpdir,
                    )
                    mock_sem.assert_called_once()
                    assert "Patched" in result, f"Expected Patched in output, got: {result}"
        print("PASS: implement semantic fallback when no path token")

    # ------------------------------------------------------------------
    # 11. Implement step — semantic_search returns no hits → [skip] message
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = make_agent(tmpdir)
        with patch.object(agent, "semantic_search", return_value=[]):
            result = agent.execute_step(
                "Implement the task reasoner edge case handling",
                repo_path=tmpdir,
            )
            assert "skip" in result.lower(), f"Expected skip when semantic returns nothing, got: {result}"
        print("PASS: implement semantic fallback returns no hits → skip")

    # ------------------------------------------------------------------
    # 12. Implement step — LLM returns unchanged content → PATCH_FAILED then
    #     retry; second call returns changed content → patch applied
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = make_agent(tmpdir)
        sample = Path(tmpdir) / "sample.py"
        original = "x = 1\n"
        sample.write_text(original, encoding="utf-8")
        mock_patch = MagicMock()
        mock_patch.diff = "@@ -1 +1 @@\n-x = 1\n+x = 2\n"
        mock_patch.applied = True
        call_count = {"n": 0}

        def _gen_patch(instruction, file_path, current_content):
            call_count["n"] += 1
            # First call returns unchanged; second (retry) returns changed
            return original if call_count["n"] == 1 else "x = 2\n"

        log_path = Path(tmpdir) / "test.log"
        agent2 = HephaestusAgent(log_path=str(log_path))
        with patch.object(agent2.task_reasoner, "generate_patch", side_effect=_gen_patch):
            with patch.object(agent2, "apply_patch", return_value=mock_patch) as mock_apply:
                result = agent2.execute_step(
                    f"Implement the changes in sample.py",
                    repo_path=tmpdir,
                )
                assert call_count["n"] == 2, f"Expected 2 generate_patch calls, got {call_count['n']}"
                mock_apply.assert_called_once()
                assert "Patched" in result, f"Expected Patched in result, got: {result}"
        log = log_path.read_text(encoding="utf-8")
        assert "PATCH_FAILED" in log, "Expected PATCH_FAILED lifecycle event in log"
        print("PASS: implement retry on unchanged LLM content")

    # ------------------------------------------------------------------
    # 13. Implement step — LLM returns unchanged on both tries → [skip]
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = make_agent(tmpdir)
        sample = Path(tmpdir) / "sample.py"
        original = "x = 1\n"
        sample.write_text(original, encoding="utf-8")
        with patch.object(agent.task_reasoner, "generate_patch", return_value=original):
            result = agent.execute_step(
                f"Implement the changes in sample.py",
                repo_path=tmpdir,
            )
            assert "skip" in result.lower() and "PATCH_FAILED" in result, \
                f"Expected skip+PATCH_FAILED when both tries unchanged, got: {result}"
        print("PASS: implement both retries unchanged → skip")

    print("\n=== execute_step tests PASSED ===")


if __name__ == "__main__":
    main()
