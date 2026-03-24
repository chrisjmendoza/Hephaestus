"""Git-aware repository context for Hephaestus."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import git
from git import InvalidGitRepositoryError, Repo


@dataclass
class GitStatus:
    """Snapshot of the working tree and staging area."""

    branch: str
    is_dirty: bool
    staged_files: list[str]
    unstaged_files: list[str]
    untracked_files: list[str]
    commit_sha: str
    commit_message: str


@dataclass
class GitCommitResult:
    """Outcome of an auto-commit operation."""

    committed: bool
    commit_sha: str
    commit_message: str
    files_committed: list[str]


class GitContext:
    """Provides git status inspection, working-tree diff, and auto-commit for agent patches."""

    def __init__(self, repo_path: str | Path = ".") -> None:
        """Open the git repository at repo_path.

        Args:
            repo_path: Root of the git repository (or any subdirectory).

        Raises:
            InvalidGitRepositoryError: If no git repo is found at or above repo_path.
        """
        self.repo: Repo = Repo(str(repo_path), search_parent_directories=True)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self) -> GitStatus:
        """Return a structured snapshot of the current working tree state."""
        repo = self.repo
        head = repo.head

        try:
            branch = head.reference.name
        except TypeError:
            branch = head.commit.hexsha[:8]  # detached HEAD

        try:
            commit_sha = head.commit.hexsha[:8]
            raw_msg = head.commit.message
            if isinstance(raw_msg, bytes):
                commit_message: str = raw_msg.decode("utf-8", errors="replace")
            elif isinstance(raw_msg, str):
                commit_message = raw_msg
            else:
                commit_message = str(raw_msg)
            commit_message = commit_message.strip().splitlines()[0]
        except ValueError:
            commit_sha = ""
            commit_message = ""

        staged = [item.a_path for item in repo.index.diff("HEAD") if item.a_path is not None]
        unstaged = [item.a_path for item in repo.index.diff(None) if item.a_path is not None]
        untracked = repo.untracked_files

        return GitStatus(
            branch=branch,
            is_dirty=repo.is_dirty(untracked_files=True),
            staged_files=staged,
            unstaged_files=unstaged,
            untracked_files=list(untracked),
            commit_sha=commit_sha,
            commit_message=commit_message,
        )

    # ------------------------------------------------------------------
    # Diff
    # ------------------------------------------------------------------

    def diff_working_tree(self, file_path: str | Path | None = None) -> str:
        """Return the unified diff of unstaged working-tree changes.

        Args:
            file_path: Limit diff to this specific file; omit for the full tree.

        Returns:
            Unified diff string, or empty string if no changes.
        """
        repo = self.repo
        kwargs: dict = {"create_patch": True}
        if file_path:
            kwargs["paths"] = [str(file_path)]
        diff_index = repo.index.diff(None, **kwargs)
        chunks: list[str] = []
        for diff in diff_index:
            try:
                raw = diff.diff
                if isinstance(raw, bytes):
                    chunks.append(raw.decode("utf-8", errors="replace"))
                elif isinstance(raw, str):
                    chunks.append(raw)
            except Exception:
                continue
        return "".join(chunks)

    def diff_staged(self) -> str:
        """Return the unified diff of staged (index vs HEAD) changes."""
        repo = self.repo
        chunks: list[str] = []
        for diff in repo.index.diff("HEAD", create_patch=True):
            try:
                raw = diff.diff
                if isinstance(raw, bytes):
                    chunks.append(raw.decode("utf-8", errors="replace"))
                elif isinstance(raw, str):
                    chunks.append(raw)
            except Exception:
                continue
        return "".join(chunks)

    # ------------------------------------------------------------------
    # Auto-commit
    # ------------------------------------------------------------------

    def commit_patch(
        self,
        file_paths: Sequence[str | Path],
        message: str,
        add_untracked: bool = True,
    ) -> GitCommitResult:
        """Stage the given files and create a commit.

        Args:
            file_paths: Files to stage (added or modified).
            message: Commit message.
            add_untracked: If True, also stage untracked files in file_paths.

        Returns:
            GitCommitResult with sha, message, and list of committed files.

        Raises:
            ValueError: If file_paths is empty.
            git.GitCommandError: If the commit fails (e.g. nothing to commit).
        """
        if not file_paths:
            raise ValueError("file_paths must not be empty")

        repo = self.repo
        str_paths = [str(p) for p in file_paths]
        repo.index.add(str_paths)
        commit = repo.index.commit(message)

        return GitCommitResult(
            committed=True,
            commit_sha=commit.hexsha[:8],
            commit_message=message,
            files_committed=str_paths,
        )
