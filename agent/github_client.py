"""GitHub API client for Hephaestus."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from github import Github, GithubException
from github.GithubException import UnknownObjectException


@dataclass
class IssueInfo:
    """Structured representation of a GitHub issue."""

    number: int
    title: str
    body: str
    labels: list[str]
    state: str
    url: str


@dataclass
class PullRequestResult:
    """Outcome of a pull request creation attempt."""

    created: bool
    number: int
    title: str
    url: str
    head_branch: str
    base_branch: str
    error: str = ""


@dataclass
class CommentResult:
    """Outcome of posting a comment on an issue or PR."""

    posted: bool
    comment_id: int = 0
    url: str = ""
    error: str = ""


@dataclass
class BranchResult:
    """Outcome of creating a remote branch."""

    created: bool
    branch_name: str
    sha: str = ""
    error: str = ""


class GitHubClient:
    """Thin wrapper around PyGithub for Hephaestus agent operations.

    Authentication uses a personal access token resolved from:
    1. The ``token`` constructor argument.
    2. The ``GITHUB_TOKEN`` environment variable.

    If neither is present the client falls back to unauthenticated access
    (rate-limited to 60 requests/hour; write operations will fail).
    """

    def __init__(self, token: str | None = None) -> None:
        resolved = token or os.environ.get("GITHUB_TOKEN", "")
        self._gh = Github(resolved) if resolved else Github()

    # ------------------------------------------------------------------
    # Issues
    # ------------------------------------------------------------------

    def get_issue(self, repo_name: str, issue_number: int) -> IssueInfo:
        """Fetch a single issue by number.

        Args:
            repo_name: Full repository name, e.g. ``"owner/repo"``.
            issue_number: GitHub issue number.

        Returns:
            Populated :class:`IssueInfo`.

        Raises:
            ValueError: If the issue or repository is not found.
            GithubException: For other API errors.
        """
        try:
            repo = self._gh.get_repo(repo_name)
            issue = repo.get_issue(issue_number)
            return IssueInfo(
                number=issue.number,
                title=issue.title,
                body=issue.body or "",
                labels=[lbl.name for lbl in issue.labels],
                state=issue.state,
                url=issue.html_url,
            )
        except UnknownObjectException as exc:
            raise ValueError(
                f"Issue #{issue_number} not found in {repo_name}"
            ) from exc

    def list_issues(
        self,
        repo_name: str,
        label: str | None = None,
        state: str = "open",
    ) -> list[IssueInfo]:
        """List issues for a repository, optionally filtered by label and state.

        Args:
            repo_name: Full repository name, e.g. ``"owner/repo"``.
            label: If provided, only issues with this label are returned.
            state: ``"open"``, ``"closed"``, or ``"all"``.

        Returns:
            List of :class:`IssueInfo` objects.
        """
        repo = self._gh.get_repo(repo_name)
        kwargs: dict = {"state": state}
        if label:
            kwargs["labels"] = [repo.get_label(label)]
        issues = repo.get_issues(**kwargs)
        return [
            IssueInfo(
                number=i.number,
                title=i.title,
                body=i.body or "",
                labels=[lbl.name for lbl in i.labels],
                state=i.state,
                url=i.html_url,
            )
            for i in issues
            if i.pull_request is None  # exclude PRs from issue list
        ]

    # ------------------------------------------------------------------
    # Comments
    # ------------------------------------------------------------------

    def post_comment(
        self, repo_name: str, issue_number: int, body: str
    ) -> CommentResult:
        """Post a comment on an issue or pull request.

        Args:
            repo_name: Full repository name.
            issue_number: Issue or PR number.
            body: Markdown comment text.

        Returns:
            :class:`CommentResult` with ``posted=True`` on success.
        """
        try:
            repo = self._gh.get_repo(repo_name)
            issue = repo.get_issue(issue_number)
            comment = issue.create_comment(body)
            return CommentResult(
                posted=True,
                comment_id=comment.id,
                url=comment.html_url,
            )
        except GithubException as exc:
            return CommentResult(posted=False, error=str(exc))

    # ------------------------------------------------------------------
    # Branches
    # ------------------------------------------------------------------

    def create_branch(
        self,
        repo_name: str,
        branch_name: str,
        base_branch: str = "main",
    ) -> BranchResult:
        """Create a remote branch from the tip of ``base_branch``.

        Args:
            repo_name: Full repository name.
            branch_name: Name of the new branch (e.g. ``"hephaestus/fix-123"``).
            base_branch: Branch to branch from. Defaults to ``"main"``.

        Returns:
            :class:`BranchResult` with ``created=True`` on success.
        """
        try:
            repo = self._gh.get_repo(repo_name)
            source = repo.get_branch(base_branch)
            ref = repo.create_git_ref(
                ref=f"refs/heads/{branch_name}",
                sha=source.commit.sha,
            )
            return BranchResult(
                created=True,
                branch_name=branch_name,
                sha=ref.object.sha,
            )
        except GithubException as exc:
            return BranchResult(
                created=False,
                branch_name=branch_name,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Pull Requests
    # ------------------------------------------------------------------

    def open_pull_request(
        self,
        repo_name: str,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str = "main",
    ) -> PullRequestResult:
        """Open a pull request from ``head_branch`` into ``base_branch``.

        Args:
            repo_name: Full repository name.
            title: PR title.
            body: PR description (Markdown).
            head_branch: Branch containing the changes.
            base_branch: Target branch for the merge. Defaults to ``"main"``.

        Returns:
            :class:`PullRequestResult` with ``created=True`` on success.
        """
        try:
            repo = self._gh.get_repo(repo_name)
            pr = repo.create_pull(
                title=title,
                body=body,
                head=head_branch,
                base=base_branch,
            )
            return PullRequestResult(
                created=True,
                number=pr.number,
                title=pr.title,
                url=pr.html_url,
                head_branch=head_branch,
                base_branch=base_branch,
            )
        except GithubException as exc:
            return PullRequestResult(
                created=False,
                number=0,
                title=title,
                url="",
                head_branch=head_branch,
                base_branch=base_branch,
                error=str(exc),
            )
