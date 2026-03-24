"""End-to-end issue resolution loop for Hephaestus.

Orchestrates the full plan → patch → test → commit → report → PR pipeline
driven by a natural-language task description (typically the body of a
GitHub issue).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from .git_context import GitCommitResult, GitContext
from .github_client import GitHubClient, IssueInfo, PullRequestResult
from .patch_executor import PatchExecutor, PatchResult
from .task_reasoner import TaskReasoner
from .task_report import TaskReport, TaskReporter
from .test_runner import TestRunResult, TestRunner

logger = logging.getLogger(__name__)


@dataclass
class ResolveResult:
    """Full outcome of a single issue resolution attempt."""

    task: str
    plan: list[str]
    patches: list[PatchResult] = field(default_factory=list)
    test_run: TestRunResult | None = None
    commit: GitCommitResult | None = None
    pull_request: PullRequestResult | None = None
    report: TaskReport | None = None
    success: bool = False
    skipped_pr: bool = False
    error: str = ""


class IssueResolver:
    """Drives plan → patch → test → commit → report → PR for a given task.

    The resolver is intentionally stateless between calls so it can be reused
    across multiple issues in a single agent session.

    Args:
        repo_path: Local path to the repository to work on.
        test_path: Relative path inside ``repo_path`` where tests live.
        dry_run: When ``True``, patches are previewed but not applied and no
            commit or PR is created.  Useful for reviewing proposed changes
            before executing them.
        github_token: Personal access token for GitHub API writes.  Falls back
            to the ``GITHUB_TOKEN`` env var when omitted.
    """

    def __init__(
        self,
        repo_path: str | Path = ".",
        test_path: str = "tests",
        dry_run: bool = False,
        github_token: str | None = None,
    ) -> None:
        self.repo_path = Path(repo_path).resolve()
        self.test_path = test_path
        self.dry_run = dry_run

        self._reasoner = TaskReasoner(
            index_path=self.repo_path / "memory" / "repo_index.json",
            embeddings_path=self.repo_path / "memory" / "repo_embeddings.json",
        )
        self._patch_executor = PatchExecutor()
        self._test_runner = TestRunner()
        self._task_reporter = TaskReporter(
            report_path=self.repo_path / "memory" / "task_report.json"
        )
        self._git = GitContext(self.repo_path)
        self._github = GitHubClient(token=github_token)

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    def resolve(
        self,
        task: str,
        patches: list[tuple[str, str]],
        branch_name: str | None = None,
        github_repo: str | None = None,
        issue_number: int | None = None,
        pr_title: str | None = None,
        pr_body: str | None = None,
        base_branch: str = "main",
    ) -> ResolveResult:
        """Run the full resolution loop for a task.

        Args:
            task: Natural-language description of the work to do.
            patches: List of ``(file_path, new_content)`` tuples to apply.
                     Pass an empty list to skip patching (plan-only mode).
            branch_name: Branch to commit onto.  If omitted no branch switch
                         is attempted — the caller is responsible for branch
                         management prior to calling this method.
            github_repo: Full GitHub repository name, e.g. ``"owner/repo"``.
                         Required to create a PR; skipped when absent.
            issue_number: GitHub issue number to reference in the PR body.
            pr_title: PR title override.  Defaults to ``"hephaestus: <task>"``.
            pr_body: PR body override.  Defaults to an auto-generated summary.
            base_branch: Target branch for the PR merge.  Defaults to ``"main"``.

        Returns:
            :class:`ResolveResult` describing every stage of the pipeline.
        """
        logger.info("RESOLVE_START task=%r", task)
        result = ResolveResult(task=task, plan=[])

        # 1. Plan
        try:
            plan = self._plan(task)
            result.plan = plan
            logger.info("RESOLVE_PLAN_COMPLETE steps=%d", len(plan))
        except Exception as exc:  # noqa: BLE001
            result.error = f"planning failed: {exc}"
            logger.error("RESOLVE_PLAN_FAILED %s", exc)
            return result

        report = self._task_reporter.start(task, plan)

        # 2. Apply patches
        applied_files: list[str] = []
        for file_path, new_content in patches:
            patch_result = self._apply_patch(file_path, new_content)
            result.patches.append(patch_result)
            self._task_reporter.record_patch(
                report,
                file_path=patch_result.file_path,
                diff=patch_result.diff,
                dry_run=patch_result.dry_run,
                applied=patch_result.applied,
            )
            if patch_result.applied:
                applied_files.append(patch_result.file_path)

        if self.dry_run:
            logger.info("RESOLVE_DRY_RUN_STOP all patches previewed, not applying")
            result.skipped_pr = True
            result.report = self._task_reporter.finish(report, "dry_run")
            self._task_reporter.persist(report)
            return result

        # 3. Run tests
        test_result = self._run_tests()
        result.test_run = test_result
        self._task_reporter.record_test(
            report,
            test_path=self.test_path,
            passed=test_result.passed,
            summary=test_result.summary,
            failed_tests=test_result.failed_tests,
        )
        logger.info(
            "RESOLVE_TESTS_COMPLETE passed=%s summary=%r",
            test_result.passed,
            test_result.summary,
        )

        if not test_result.passed:
            logger.warning("RESOLVE_TESTS_FAILED — skipping commit and PR")
            result.error = f"tests failed: {test_result.summary}"
            result.report = self._task_reporter.finish(report, "tests_failed")
            self._task_reporter.persist(report)
            return result

        # 4. Commit
        if applied_files:
            commit_message = self._build_commit_message(task, plan)
            commit_result = self._commit(applied_files, commit_message)
            result.commit = commit_result
            if commit_result.committed:
                self._task_reporter.record_commit(
                    report,
                    commit_sha=commit_result.commit_sha,
                    commit_message=commit_result.commit_message,
                    files_committed=commit_result.files_committed,
                )
                logger.info("RESOLVE_COMMIT_COMPLETE sha=%s", commit_result.commit_sha)

        # 5. Open PR
        if github_repo and not self.dry_run:
            eff_branch = branch_name or self._current_branch()
            eff_title = pr_title or f"hephaestus: {task}"
            eff_body = pr_body or self._build_pr_body(
                task, plan, result, issue_number
            )
            pr_result = self._open_pr(
                github_repo, eff_title, eff_body, eff_branch, base_branch
            )
            result.pull_request = pr_result
            if pr_result.created:
                logger.info("RESOLVE_PR_COMPLETE #%d %s", pr_result.number, pr_result.url)
            else:
                logger.warning("RESOLVE_PR_FAILED %s", pr_result.error)
        else:
            result.skipped_pr = True
            logger.info(
                "RESOLVE_PR_SKIPPED github_repo=%s dry_run=%s",
                github_repo,
                self.dry_run,
            )

        # 6. Finish report
        outcome = "success" if (not result.error) else "partial"
        result.report = self._task_reporter.finish(report, outcome)
        self._task_reporter.persist(report)
        result.success = not bool(result.error)

        logger.info("RESOLVE_COMPLETE success=%s", result.success)
        return result

    def resolve_issue(
        self,
        issue: IssueInfo,
        patches: list[tuple[str, str]],
        github_repo: str,
        branch_name: str | None = None,
        base_branch: str = "main",
    ) -> ResolveResult:
        """Convenience wrapper that resolves from a fetched :class:`IssueInfo`.

        Derives the task description from the issue title + body and
        automatically references the issue number in the PR body.

        Args:
            issue: Fetched GitHub issue.
            patches: List of ``(file_path, new_content)`` tuples.
            github_repo: Full repository name, e.g. ``"owner/repo"``.
            branch_name: Branch for the commit/PR.
            base_branch: Merge target.

        Returns:
            :class:`ResolveResult`.
        """
        task = f"#{issue.number}: {issue.title}"
        if issue.body:
            task += f"\n\n{issue.body}"

        return self.resolve(
            task=task,
            patches=patches,
            branch_name=branch_name,
            github_repo=github_repo,
            issue_number=issue.number,
            base_branch=base_branch,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _plan(self, task: str) -> list[str]:
        return self._reasoner.generate_plan(task, repo_path=str(self.repo_path))

    def _apply_patch(self, file_path: str, new_content: str) -> PatchResult:
        return self._patch_executor.apply(file_path, new_content, dry_run=self.dry_run)

    def _run_tests(self) -> TestRunResult:
        full_test_path = self.repo_path / self.test_path
        return self._test_runner.run(str(full_test_path))

    def _commit(self, files: list[str], message: str) -> GitCommitResult:
        return self._git.commit_patch(files, message)

    def _current_branch(self) -> str:
        try:
            return self._git.repo.active_branch.name
        except TypeError:
            return "main"

    @staticmethod
    def _build_commit_message(task: str, plan: list[str]) -> str:
        first_line = task.splitlines()[0][:72]
        steps = "\n".join(f"- {s}" for s in plan[:5])
        return f"hephaestus: {first_line}\n\nPlan:\n{steps}"

    @staticmethod
    def _build_pr_body(
        task: str,
        plan: list[str],
        result: ResolveResult,
        issue_number: int | None,
    ) -> str:
        lines: list[str] = ["## Hephaestus automated patch\n"]

        if issue_number:
            lines.append(f"Closes #{issue_number}\n")

        lines.append(f"**Task:** {task.splitlines()[0]}\n")

        lines.append("### Plan")
        for i, step in enumerate(plan, 1):
            lines.append(f"{i}. {step}")
        lines.append("")

        lines.append("### Patches applied")
        if result.patches:
            for p in result.patches:
                status = "applied" if p.applied else "skipped (dry-run)"
                lines.append(f"- `{p.file_path}` — {status}")
        else:
            lines.append("- none")
        lines.append("")

        if result.test_run:
            icon = "✅" if result.test_run.passed else "❌"
            lines.append(f"### Tests\n{icon} {result.test_run.summary}")

        return "\n".join(lines)

    def _open_pr(
        self,
        github_repo: str,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str,
    ) -> PullRequestResult:
        return self._github.open_pull_request(
            github_repo, title, body, head_branch, base_branch=base_branch
        )
