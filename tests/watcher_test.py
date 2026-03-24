"""Tests for IssueWatcher: poll, handle, state persistence."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from agent.github_client import CommentResult, IssueInfo
    from agent.watcher import DEFAULT_INTERVAL, DEFAULT_LABEL, IssueWatcher

    # ------------------------------------------------------------------ #
    print("Test 1: poll_once() with no issues does nothing")
    with tempfile.TemporaryDirectory() as tmpdir:
        watcher = _make_watcher("owner/repo", tmpdir)

        with patch.object(watcher._github, "list_issues", return_value=[]):
            handled = watcher.poll_once()

        assert handled == [], handled
    print("  PASS")

    # ------------------------------------------------------------------ #
    print("Test 2: poll_once() handles a new labeled issue")
    with tempfile.TemporaryDirectory() as tmpdir:
        watcher = _make_watcher("owner/repo", tmpdir)
        issue = _make_issue(42, "Add login page", "Users need a login form")

        with patch.object(watcher._github, "list_issues", return_value=[issue]):
            with patch.object(watcher, "_handle_issue") as mock_handle:
                handled = watcher.poll_once()

        mock_handle.assert_called_once_with(issue)
        assert handled == [42], handled
    print("  PASS")

    # ------------------------------------------------------------------ #
    print("Test 3: already-processed issues are skipped")
    with tempfile.TemporaryDirectory() as tmpdir:
        watcher = _make_watcher("owner/repo", tmpdir)
        watcher._processed.add(42)
        issue = _make_issue(42, "Add login page", "Users need a login form")

        with patch.object(watcher._github, "list_issues", return_value=[issue]):
            with patch.object(watcher, "_handle_issue") as mock_handle:
                handled = watcher.poll_once()

        mock_handle.assert_not_called()
        assert handled == [], handled
    print("  PASS")

    # ------------------------------------------------------------------ #
    print("Test 4: poll error is logged, not raised")
    with tempfile.TemporaryDirectory() as tmpdir:
        watcher = _make_watcher("owner/repo", tmpdir)

        with patch.object(watcher._github, "list_issues", side_effect=RuntimeError("network")):
            handled = watcher.poll_once()  # must not raise

        assert handled == [], handled
    print("  PASS")

    # ------------------------------------------------------------------ #
    print("Test 5: state is persisted and reloaded across instances")
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "memory" / "watcher_state.json"

        w1 = _make_watcher("owner/repo", tmpdir, state_path=state_path)
        w1._processed.add(10)
        w1._processed.add(20)
        w1._save_state()

        w2 = _make_watcher("owner/repo", tmpdir, state_path=state_path)
        assert 10 in w2._processed, w2._processed
        assert 20 in w2._processed, w2._processed
    print("  PASS")

    # ------------------------------------------------------------------ #
    print("Test 6: state for different repos is kept separate")
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "memory" / "watcher_state.json"

        wa = _make_watcher("owner/alpha", tmpdir, state_path=state_path)
        wa._processed.add(1)
        wa._save_state()

        wb = _make_watcher("owner/beta", tmpdir, state_path=state_path)
        wb._processed.add(2)
        wb._save_state()

        # Re-load alpha — should only have issue 1
        wa2 = _make_watcher("owner/alpha", tmpdir, state_path=state_path)
        assert 1 in wa2._processed
        assert 2 not in wa2._processed
    print("  PASS")

    # ------------------------------------------------------------------ #
    print("Test 7: _handle_issue posts acknowledgement comment")
    with tempfile.TemporaryDirectory() as tmpdir:
        watcher = _make_watcher("owner/repo", tmpdir)
        issue = _make_issue(7, "Fix crash on startup", "App crashes when config missing")

        posted_comments: list[str] = []

        def fake_comment(repo, number, body):
            posted_comments.append(body)
            return CommentResult(posted=True, comment_id=1)

        with patch.object(watcher._github, "post_comment", side_effect=fake_comment):
            with patch.object(watcher._repo_manager, "ensure_workspace") as wsp:
                wsp.side_effect = RuntimeError("no workspace")  # abort after ack
                try:
                    watcher._handle_issue(issue)
                except Exception:
                    pass  # error comment path

        assert any("picked up" in c.lower() for c in posted_comments), posted_comments
        assert 7 in watcher._processed
    print("  PASS")

    # ------------------------------------------------------------------ #
    print("Test 8: _post_result includes plan steps in comment")
    with tempfile.TemporaryDirectory() as tmpdir:
        from agent.issue_resolver import ResolveResult

        watcher = _make_watcher("owner/repo", tmpdir)
        issue = _make_issue(8, "Add tests", "")
        result = ResolveResult(
            task="Add tests",
            plan=["Step one", "Step two"],
            success=False,
            error="",
        )

        posted: list[str] = []
        with patch.object(
            watcher._github, "post_comment",
            side_effect=lambda r, n, b: posted.append(b) or CommentResult(posted=True),
        ):
            watcher._post_result(issue, result)

        assert posted, "No comment was posted"
        assert "Step one" in posted[0], posted[0]
        assert "Step two" in posted[0], posted[0]
    print("  PASS")

    # ------------------------------------------------------------------ #
    print("Test 9: DEFAULT_LABEL and DEFAULT_INTERVAL values are correct")
    assert DEFAULT_LABEL == "hephaestus/auto", DEFAULT_LABEL
    assert DEFAULT_INTERVAL == 300, DEFAULT_INTERVAL
    print("  PASS")

    # ------------------------------------------------------------------ #
    print("Test 10: run_forever() stops after stop_after cycles")
    with tempfile.TemporaryDirectory() as tmpdir:
        watcher = _make_watcher("owner/repo", tmpdir)

        poll_calls: list[int] = []

        def fake_poll():
            poll_calls.append(1)
            return []

        with patch.object(watcher, "poll_once", side_effect=fake_poll):
            with patch("time.sleep"):  # skip real sleep
                watcher.run_forever(stop_after=3)

        assert len(poll_calls) == 3, poll_calls
    print("  PASS")

    print("\nAll watcher tests passed.")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_watcher(
    repo_name: str,
    tmpdir: str,
    state_path: Path | None = None,
) -> "IssueWatcher":  # noqa: F821
    from agent.watcher import IssueWatcher

    sp = state_path or Path(tmpdir) / "memory" / "watcher_state.json"
    return IssueWatcher(
        repo_name,
        workspace_root=Path(tmpdir) / "workspace",
        state_path=sp,
    )


def _make_issue(number: int, title: str, body: str) -> "IssueInfo":  # noqa: F821
    from agent.github_client import IssueInfo

    return IssueInfo(
        number=number,
        title=title,
        body=body,
        labels=["hephaestus/auto"],
        state="open",
        url=f"https://github.com/owner/repo/issues/{number}",
    )


if __name__ == "__main__":
    main()
