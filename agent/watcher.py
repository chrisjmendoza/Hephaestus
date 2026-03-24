"""Issue watcher daemon for Hephaestus.

Polls a GitHub repository for issues labeled with a trigger label (default:
``hephaestus/auto``) and runs the full resolution pipeline for each new
issue found.

Usage (via CLI)::

    python main.py watch owner/repo
    python main.py watch owner/repo --label hephaestus/auto --interval 300

Design
------
* State (processed issue numbers) is persisted to
  ``memory/watcher_state.json`` so restarts never re-process issues that
  were already picked up.
* Each issue is marked processed **before** the pipeline runs — a crash
  mid-run will not re-trigger the same issue on restart.
* The workspace is kept up to date via :meth:`RepoManager.ensure_workspace`
  which pulls an existing clone rather than re-cloning, keeping large
  repositories fast.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from .github_client import GitHubClient, IssueInfo
from .issue_resolver import IssueResolver, ResolveResult
from .repo_manager import RepoManager

logger = logging.getLogger(__name__)

DEFAULT_LABEL = "hephaestus/auto"
DEFAULT_INTERVAL = 300  # 5 minutes


class IssueWatcher:
    """Polls GitHub and runs :class:`IssueResolver` for each newly labeled issue.

    Args:
        repo_name: Full GitHub repository name, e.g. ``"owner/repo"``.
        label: Label that triggers resolution.  Issues carrying this label
            that have not been processed yet will be picked up on the next
            poll.
        poll_interval: Seconds between poll cycles.
        workspace_root: Root directory for local clones (passed to
            :class:`RepoManager`).
        state_path: Path to the JSON file that records processed issue numbers
            so they survive restarts.
        github_token: GitHub PAT for API calls and authenticated cloning.
            Falls back to the ``GITHUB_TOKEN`` environment variable.
    """

    def __init__(
        self,
        repo_name: str,
        *,
        label: str = DEFAULT_LABEL,
        poll_interval: int = DEFAULT_INTERVAL,
        workspace_root: str | Path = "workspace",
        state_path: str | Path = "memory/watcher_state.json",
        github_token: str | None = None,
    ) -> None:
        self.repo_name = repo_name
        self.label = label
        self.poll_interval = poll_interval
        self.state_path = Path(state_path)
        self._github = GitHubClient(token=github_token)
        self._repo_manager = RepoManager(workspace_root=workspace_root)
        self._github_token = github_token
        self._processed: set[int] = set()
        self._load_state()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def poll_once(self) -> list[int]:
        """Run a single poll cycle and process any new labeled issues.

        Returns:
            List of issue numbers that were handled in this cycle.
        """
        logger.info(
            "WATCHER_POLL_START repo=%s label=%r", self.repo_name, self.label
        )
        try:
            issues = self._github.list_issues(
                self.repo_name, label=self.label, state="open"
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("WATCHER_POLL_ERROR %s", exc)
            return []

        handled: list[int] = []
        for issue in issues:
            if issue.number not in self._processed:
                self._handle_issue(issue)
                handled.append(issue.number)

        logger.info("WATCHER_POLL_COMPLETE handled=%d", len(handled))
        return handled

    def run_forever(self, *, stop_after: int | None = None) -> None:
        """Block, poll, and sleep indefinitely.  Ctrl-C exits cleanly.

        Args:
            stop_after: When set, stop after this many poll cycles.  Primarily
                useful for integration tests.
        """
        logger.info(
            "WATCHER_START repo=%s label=%r interval=%ds",
            self.repo_name,
            self.label,
            self.poll_interval,
        )
        print(
            f"Watching {self.repo_name!r} for issues labeled {self.label!r}\n"
            f"Polling every {self.poll_interval}s — Ctrl-C to stop\n"
        )
        cycles = 0
        try:
            while True:
                self.poll_once()
                cycles += 1
                if stop_after is not None and cycles >= stop_after:
                    break
                time.sleep(self.poll_interval)
        except KeyboardInterrupt:
            logger.info("WATCHER_STOP user interrupted")
            print("\nWatcher stopped.")

    # ------------------------------------------------------------------
    # Issue handling
    # ------------------------------------------------------------------

    def _handle_issue(self, issue: IssueInfo) -> None:
        """Process a single issue through the full resolution pipeline."""
        logger.info("WATCHER_ISSUE_START #%d %r", issue.number, issue.title)

        # Mark processed before the pipeline so a crash doesn't re-trigger it.
        self._processed.add(issue.number)
        self._save_state()

        # Acknowledge on GitHub immediately so the user knows it was picked up.
        self._github.post_comment(
            self.repo_name,
            issue.number,
            (
                "**Hephaestus** picked up this issue — working on it.\n\n"
                "I'll comment again once I have a plan and PR ready."
            ),
        )

        try:
            workspace = self._repo_manager.ensure_workspace(
                self.repo_name,
                github_token=self._github_token,
            )
            repo_path = workspace.local_path

            branch_name = f"hephaestus/issue-{issue.number}"
            self._repo_manager.checkout_branch(
                self.repo_name, branch_name, create=True
            )

            task = (
                f"{issue.title}\n\n{issue.body}".strip()
                if issue.body
                else issue.title
            )
            resolver = IssueResolver(
                repo_path=repo_path,
                github_token=self._github_token,
            )
            result = resolver.resolve(
                task=task,
                patches=[],
                branch_name=branch_name,
                github_repo=self.repo_name,
                issue_number=issue.number,
            )

            self._post_result(issue, result)
            logger.info(
                "WATCHER_ISSUE_COMPLETE #%d success=%s", issue.number, result.success
            )

        except Exception as exc:  # noqa: BLE001
            logger.error("WATCHER_ISSUE_FAILED #%d %s", issue.number, exc)
            self._github.post_comment(
                self.repo_name,
                issue.number,
                (
                    "**Hephaestus** encountered an error while handling this issue:\n\n"
                    f"```\n{exc}\n```"
                ),
            )

    def _post_result(self, issue: IssueInfo, result: ResolveResult) -> None:
        """Post a formatted summary comment on the issue."""
        lines: list[str] = ["## Hephaestus — Resolution Summary\n"]

        if result.plan:
            lines.append("### Plan\n")
            for i, step in enumerate(result.plan, 1):
                lines.append(f"{i}. {step}")
            lines.append("")

        if result.pull_request and result.pull_request.created:
            lines.append(f"**PR ready:** {result.pull_request.url}")
        elif result.error:
            lines.append(f"**Status:** ⚠️ {result.error}")
        else:
            lines.append(
                "**Status:** Plan generated. "
                "Code patches will be applied in a future run once code generation is available."
            )

        self._github.post_comment(
            self.repo_name, issue.number, "\n".join(lines)
        )

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------

    def _load_state(self) -> None:
        """Load processed issue numbers from the state file."""
        if not self.state_path.exists():
            self._processed = set()
            return
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            self._processed = set(data.get(self.repo_name, []))
            logger.info(
                "WATCHER_STATE_LOADED repo=%s processed=%d",
                self.repo_name,
                len(self._processed),
            )
        except Exception:  # noqa: BLE001
            self._processed = set()

    def _save_state(self) -> None:
        """Persist the current set of processed issue numbers."""
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            existing: dict = {}
            if self.state_path.exists():
                existing = json.loads(
                    self.state_path.read_text(encoding="utf-8")
                )
            existing[self.repo_name] = sorted(self._processed)
            self.state_path.write_text(
                json.dumps(existing, indent=2), encoding="utf-8"
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("WATCHER_STATE_SAVE_ERROR %s", exc)
