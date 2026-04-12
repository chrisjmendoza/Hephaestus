"""Tests for the resolve CLI command argument parsing and dispatch."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


def main() -> None:
    """Test resolve CLI argument parsing and agent dispatch."""
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    import main as cli_main

    # ------------------------------------------------------------------
    # 1. Missing issue number → usage message, no crash
    # ------------------------------------------------------------------
    with patch("sys.argv", ["main.py", "resolve"]):
        output = []
        with patch("builtins.print", side_effect=output.append):
            cli_main.main()
        assert any("Usage" in str(line) for line in output), \
            f"Expected usage message, got: {output}"
    print("PASS: missing issue number shows usage")

    # ------------------------------------------------------------------
    # 2. Non-numeric issue number → usage message
    # ------------------------------------------------------------------
    with patch("sys.argv", ["main.py", "resolve", "not-a-number"]):
        output = []
        with patch("builtins.print", side_effect=output.append):
            cli_main.main()
        assert any("Usage" in str(line) for line in output), \
            f"Expected usage message, got: {output}"
    print("PASS: non-numeric issue number shows usage")

    # ------------------------------------------------------------------
    # 3. Valid issue number, local only (no --github-repo)
    # ------------------------------------------------------------------
    with patch("sys.argv", ["main.py", "resolve", "42", "--dry-run"]):
        mock_plan = ["Analyze the issue", "Implement fix", "Run tests"]
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.error = None
        mock_result.pull_request = None

        with patch("agent.agent.HephaestusAgent.generate_task_plan", return_value=mock_plan):
            with patch("agent.agent.HephaestusAgent.resolve_issue", return_value=mock_result) as mock_resolve:
                output = []
                with patch("builtins.print", side_effect=output.append):
                    cli_main.main()
                mock_resolve.assert_called_once()
                call_kwargs = mock_resolve.call_args.kwargs
                assert call_kwargs["issue_number"] == 42
                assert call_kwargs["dry_run"] is True
                assert call_kwargs["github_repo"] is None
                assert any("Resolved" in str(line) for line in output), \
                    f"Expected success message, got: {output}"
    print("PASS: local resolve with dry-run dispatches correctly")

    # ------------------------------------------------------------------
    # 4. With --github-repo: fetches issue then resolves
    # ------------------------------------------------------------------
    with patch("sys.argv", ["main.py", "resolve", "7", "--github-repo", "owner/repo"]):
        mock_issue = MagicMock()
        mock_issue.title = "Fix the thing"
        mock_issue.body = "It is broken"
        mock_plan = ["Analyze requirements", "Apply fix"]
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.pull_request = MagicMock()
        mock_result.pull_request.url = "https://github.com/owner/repo/pull/99"

        with patch("agent.agent.HephaestusAgent.gh_get_issue", return_value=mock_issue):
            with patch("agent.agent.HephaestusAgent.generate_task_plan", return_value=mock_plan):
                with patch("agent.agent.HephaestusAgent.resolve_issue", return_value=mock_result) as mock_resolve:
                    output = []
                    with patch("builtins.print", side_effect=output.append):
                        cli_main.main()
                    call_kwargs = mock_resolve.call_args.kwargs
                    assert call_kwargs["github_repo"] == "owner/repo"
                    assert call_kwargs["issue_number"] == 7
                    assert "Fix the thing" in call_kwargs["task"]
                    assert any("pull/99" in str(line) for line in output), \
                        f"Expected PR URL in output, got: {output}"
    print("PASS: github-repo resolve fetches issue and prints PR URL")

    # ------------------------------------------------------------------
    # 5. resolve_issue failure → prints error message
    # ------------------------------------------------------------------
    with patch("sys.argv", ["main.py", "resolve", "5"]):
        mock_plan = ["Analyze"]
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error = "patch failed: file not found"

        with patch("agent.agent.HephaestusAgent.generate_task_plan", return_value=mock_plan):
            with patch("agent.agent.HephaestusAgent.resolve_issue", return_value=mock_result):
                output = []
                with patch("builtins.print", side_effect=output.append):
                    cli_main.main()
                assert any("failed" in str(line).lower() for line in output), \
                    f"Expected failure message, got: {output}"
    print("PASS: failed resolve prints error")

    print("\n=== resolve CLI tests PASSED ===")


if __name__ == "__main__":
    main()
