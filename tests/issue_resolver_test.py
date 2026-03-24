"""Tests for IssueResolver: end-to-end plan → patch → test → commit → PR pipeline."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch


def _make_mock_github() -> MagicMock:
    """Return a Github mock that reports success for all write operations."""
    mock_gh = MagicMock()
    mock_repo = mock_gh.get_repo.return_value

    mock_pr = MagicMock()
    mock_pr.number = 99
    mock_pr.title = "hephaestus: test task"
    mock_pr.html_url = "https://github.com/owner/repo/pull/99"
    mock_repo.create_pull.return_value = mock_pr

    mock_branch = MagicMock()
    mock_branch.commit.sha = "deadbeef"
    mock_repo.get_branch.return_value = mock_branch

    mock_ref = MagicMock()
    mock_ref.object.sha = "deadbeef"
    mock_repo.create_git_ref.return_value = mock_ref

    return mock_gh


def _init_git_repo(path: Path):
    """Create a minimal git repo with one commit."""
    import git

    repo = git.Repo.init(str(path))
    repo.config_writer().set_value("user", "name", "Hephaestus Test").release()
    repo.config_writer().set_value("user", "email", "test@hephaestus.local").release()
    readme = path / "README.md"
    readme.write_text("# Test repo\n", encoding="utf-8")
    repo.index.add(["README.md"])
    repo.index.commit("initial commit")
    return repo


def main() -> None:
    """Run all IssueResolver tests."""
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from agent.issue_resolver import IssueResolver
    from agent.github_client import IssueInfo

    # ------------------------------------------------------------------ #
    print("Test 1: dry_run=True — patches previewed, no commit or PR")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        repo_root = Path(tmpdir)
        git_repo = _init_git_repo(repo_root)

        # Create minimal memory dir so TaskReasoner doesn't crash
        (repo_root / "memory").mkdir()

        target_file = repo_root / "hello.txt"
        target_file.write_text("old content\n", encoding="utf-8")

        with (
            patch("agent.issue_resolver.TaskReasoner") as mock_reasoner_cls,
            patch("agent.issue_resolver.GitHubClient"),
        ):
            mock_reasoner_cls.return_value.generate_plan.return_value = [
                "Step A", "Step B"
            ]

            resolver = IssueResolver(repo_path=repo_root, dry_run=True)
            result = resolver.resolve(
                task="update hello file",
                patches=[(str(target_file), "new content\n")],
            )

        assert result.skipped_pr is True, "dry_run should skip PR"
        assert len(result.patches) == 1
        assert result.patches[0].dry_run is True
        assert result.patches[0].applied is False
        # File must NOT be modified
        assert target_file.read_text(encoding="utf-8") == "old content\n"

        git_repo.close()
    print("  PASS")

    # ------------------------------------------------------------------ #
    print("Test 2: patches applied, tests pass → commit, no PR (no github_repo)")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        repo_root = Path(tmpdir)
        git_repo = _init_git_repo(repo_root)
        (repo_root / "memory").mkdir()

        target_file = repo_root / "hello.txt"
        target_file.write_text("old content\n", encoding="utf-8")

        mock_test_result = MagicMock()
        mock_test_result.passed = True
        mock_test_result.summary = "1 passed"
        mock_test_result.failed_tests = []

        with (
            patch("agent.issue_resolver.TaskReasoner") as mock_reasoner_cls,
            patch("agent.issue_resolver.TestRunner") as mock_runner_cls,
            patch("agent.issue_resolver.GitHubClient"),
        ):
            mock_reasoner_cls.return_value.generate_plan.return_value = ["Step A"]
            mock_runner_cls.return_value.run.return_value = mock_test_result

            resolver = IssueResolver(repo_path=repo_root, dry_run=False)
            result = resolver.resolve(
                task="update hello file",
                patches=[(str(target_file), "new content\n")],
                github_repo=None,
            )

        assert result.patches[0].applied is True
        assert target_file.read_text(encoding="utf-8") == "new content\n"
        assert result.test_run is not None
        assert result.test_run.passed is True
        assert result.commit is not None
        assert result.commit.committed is True
        assert result.pull_request is None
        assert result.skipped_pr is True

        git_repo.close()
    print("  PASS")

    # ------------------------------------------------------------------ #
    print("Test 3: tests fail → no commit, no PR, error set")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        repo_root = Path(tmpdir)
        git_repo = _init_git_repo(repo_root)
        (repo_root / "memory").mkdir()

        target_file = repo_root / "hello.txt"
        target_file.write_text("original\n", encoding="utf-8")

        mock_test_result = MagicMock()
        mock_test_result.passed = False
        mock_test_result.summary = "1 failed"
        mock_test_result.failed_tests = ["test_something"]

        with (
            patch("agent.issue_resolver.TaskReasoner") as mock_reasoner_cls,
            patch("agent.issue_resolver.TestRunner") as mock_runner_cls,
            patch("agent.issue_resolver.GitHubClient"),
        ):
            mock_reasoner_cls.return_value.generate_plan.return_value = ["Step A"]
            mock_runner_cls.return_value.run.return_value = mock_test_result

            resolver = IssueResolver(repo_path=repo_root, dry_run=False)
            result = resolver.resolve(
                task="break things",
                patches=[(str(target_file), "broken\n")],
            )

        assert result.commit is None
        assert result.pull_request is None
        assert result.success is False
        assert "tests failed" in result.error

        git_repo.close()
    print("  PASS")

    # ------------------------------------------------------------------ #
    print("Test 4: full pipeline with github_repo → PR opened")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        repo_root = Path(tmpdir)
        git_repo = _init_git_repo(repo_root)
        (repo_root / "memory").mkdir()

        target_file = repo_root / "hello.txt"
        target_file.write_text("old\n", encoding="utf-8")

        mock_test_result = MagicMock()
        mock_test_result.passed = True
        mock_test_result.summary = "all passed"
        mock_test_result.failed_tests = []

        with (
            patch("agent.issue_resolver.TaskReasoner") as mock_reasoner_cls,
            patch("agent.issue_resolver.TestRunner") as mock_runner_cls,
            patch("agent.issue_resolver.GitHubClient") as mock_gh_cls,
        ):
            mock_reasoner_cls.return_value.generate_plan.return_value = ["Step A"]
            mock_runner_cls.return_value.run.return_value = mock_test_result

            # Wire up mock PR result
            mock_gh_instance = mock_gh_cls.return_value
            mock_pr_result = MagicMock()
            mock_pr_result.created = True
            mock_pr_result.number = 99
            mock_pr_result.url = "https://github.com/owner/repo/pull/99"
            mock_pr_result.error = ""
            mock_gh_instance.open_pull_request.return_value = mock_pr_result

            resolver = IssueResolver(repo_path=repo_root, dry_run=False)
            result = resolver.resolve(
                task="fix issue 42",
                patches=[(str(target_file), "fixed\n")],
                github_repo="owner/repo",
                issue_number=42,
            )

        assert result.success is True
        assert result.pull_request is not None
        assert result.pull_request.created is True
        assert result.pull_request.number == 99
        assert result.skipped_pr is False

        git_repo.close()
    print("  PASS")

    # ------------------------------------------------------------------ #
    print("Test 5: resolve_issue() convenience wrapper derives task from IssueInfo")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        repo_root = Path(tmpdir)
        git_repo = _init_git_repo(repo_root)
        (repo_root / "memory").mkdir()

        issue = IssueInfo(
            number=7,
            title="Add greeting",
            body="Please add a greeting message.",
            labels=["enhancement"],
            state="open",
            url="https://github.com/owner/repo/issues/7",
        )

        mock_test_result = MagicMock()
        mock_test_result.passed = True
        mock_test_result.summary = "ok"
        mock_test_result.failed_tests = []

        with (
            patch("agent.issue_resolver.TaskReasoner") as mock_reasoner_cls,
            patch("agent.issue_resolver.TestRunner") as mock_runner_cls,
            patch("agent.issue_resolver.GitHubClient") as mock_gh_cls,
        ):
            mock_reasoner_cls.return_value.generate_plan.return_value = ["greet"]
            mock_runner_cls.return_value.run.return_value = mock_test_result

            mock_pr_result = MagicMock()
            mock_pr_result.created = True
            mock_pr_result.number = 8
            mock_pr_result.url = "https://github.com/owner/repo/pull/8"
            mock_pr_result.error = ""
            mock_gh_cls.return_value.open_pull_request.return_value = mock_pr_result

            resolver = IssueResolver(repo_path=repo_root, dry_run=False)
            result = resolver.resolve_issue(
                issue=issue,
                patches=[],
                github_repo="owner/repo",
            )

        assert "#7" in result.task
        assert "Add greeting" in result.task

        git_repo.close()
    print("  PASS")

    print("\nAll issue_resolver tests passed.")


if __name__ == "__main__":
    main()
