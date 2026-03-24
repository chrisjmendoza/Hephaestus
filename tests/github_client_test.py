"""Tests for GitHubClient: issue fetch, comment, branch creation, PR opening."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


def _make_mock_github() -> MagicMock:
    """Return a mock Github instance wired with sensible defaults."""
    mock_gh = MagicMock()

    # mock issue
    mock_label = MagicMock()
    mock_label.name = "bug"

    mock_issue = MagicMock()
    mock_issue.number = 42
    mock_issue.title = "Fix the thing"
    mock_issue.body = "It is broken."
    mock_issue.labels = [mock_label]
    mock_issue.state = "open"
    mock_issue.html_url = "https://github.com/owner/repo/issues/42"
    mock_issue.pull_request = None

    mock_repo = mock_gh.get_repo.return_value
    mock_repo.get_issue.return_value = mock_issue
    mock_repo.get_issues.return_value = [mock_issue]

    # mock comment
    mock_comment = MagicMock()
    mock_comment.id = 999
    mock_comment.html_url = "https://github.com/owner/repo/issues/42#issuecomment-999"
    mock_issue.create_comment.return_value = mock_comment

    # mock branch creation
    mock_branch = MagicMock()
    mock_branch.commit.sha = "abc123"
    mock_repo.get_branch.return_value = mock_branch

    mock_ref = MagicMock()
    mock_ref.object.sha = "abc123"
    mock_repo.create_git_ref.return_value = mock_ref

    # mock PR
    mock_pr = MagicMock()
    mock_pr.number = 7
    mock_pr.title = "Fix the thing"
    mock_pr.html_url = "https://github.com/owner/repo/pull/7"
    mock_repo.create_pull.return_value = mock_pr

    return mock_gh


def main() -> None:
    """Run all GitHubClient tests."""
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from agent.github_client import GitHubClient

    print("Test 1: get_issue returns IssueInfo")
    with patch("agent.github_client.Github", return_value=_make_mock_github()):
        client = GitHubClient(token="fake-token")
        issue = client.get_issue("owner/repo", 42)
        assert issue.number == 42, f"expected 42, got {issue.number}"
        assert issue.title == "Fix the thing"
        assert issue.body == "It is broken."
        assert issue.labels == ["bug"]
        assert issue.state == "open"
        assert "issues/42" in issue.url
    print("  PASS")

    print("Test 2: list_issues returns list of IssueInfo")
    with patch("agent.github_client.Github", return_value=_make_mock_github()):
        client = GitHubClient(token="fake-token")
        issues = client.list_issues("owner/repo")
        assert len(issues) == 1
        assert issues[0].number == 42
    print("  PASS")

    print("Test 3: post_comment returns CommentResult with posted=True")
    with patch("agent.github_client.Github", return_value=_make_mock_github()):
        client = GitHubClient(token="fake-token")
        result = client.post_comment("owner/repo", 42, "Working on it!")
        assert result.posted is True
        assert result.comment_id == 999
        assert "issuecomment" in result.url
    print("  PASS")

    print("Test 4: create_branch returns BranchResult with created=True")
    with patch("agent.github_client.Github", return_value=_make_mock_github()):
        client = GitHubClient(token="fake-token")
        result = client.create_branch("owner/repo", "hephaestus/fix-42")
        assert result.created is True
        assert result.branch_name == "hephaestus/fix-42"
        assert result.sha == "abc123"
    print("  PASS")

    print("Test 5: open_pull_request returns PullRequestResult with created=True")
    with patch("agent.github_client.Github", return_value=_make_mock_github()):
        client = GitHubClient(token="fake-token")
        result = client.open_pull_request(
            "owner/repo",
            title="Fix the thing",
            body="Resolves #42",
            head_branch="hephaestus/fix-42",
            base_branch="main",
        )
        assert result.created is True
        assert result.number == 7
        assert "pull/7" in result.url
        assert result.head_branch == "hephaestus/fix-42"
        assert result.base_branch == "main"
    print("  PASS")

    print("Test 6: post_comment gracefully handles API error")
    from github import GithubException

    with patch("agent.github_client.Github") as mock_class:
        mock_gh = MagicMock()
        mock_repo = mock_gh.get_repo.return_value
        mock_issue = MagicMock()
        mock_issue.create_comment.side_effect = GithubException(
            403, {"message": "Forbidden"}, None
        )
        mock_repo.get_issue.return_value = mock_issue
        mock_class.return_value = mock_gh

        client = GitHubClient(token="fake-token")
        result = client.post_comment("owner/repo", 42, "oops")
        assert result.posted is False
        assert result.error != ""
    print("  PASS")

    print("Test 7: open_pull_request gracefully handles API error")
    with patch("agent.github_client.Github") as mock_class:
        mock_gh = MagicMock()
        mock_repo = mock_gh.get_repo.return_value
        mock_repo.create_pull.side_effect = GithubException(
            422, {"message": "Validation Failed"}, None
        )
        mock_class.return_value = mock_gh

        client = GitHubClient(token="fake-token")
        result = client.open_pull_request(
            "owner/repo", "title", "body", "head", "main"
        )
        assert result.created is False
        assert result.error != ""
    print("  PASS")

    print("\nAll github_client tests passed.")


if __name__ == "__main__":
    main()
