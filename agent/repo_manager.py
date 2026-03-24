"""Target repository manager for Hephaestus.

Manages local working copies of external repositories so the agent can
operate on any project without contaminating the Hephaestus codebase.

Workspaces are stored under a configurable root directory
(default: ``workspace/`` relative to the Hephaestus project).  Each repo
gets its own subdirectory keyed by ``owner/name``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import git
from git import InvalidGitRepositoryError, Repo

logger = logging.getLogger(__name__)


@dataclass
class WorkspaceInfo:
    """Describes the state of a managed local repository workspace."""

    repo_name: str
    local_path: Path
    branch: str
    commit_sha: str
    freshly_cloned: bool


@dataclass
class BranchCheckoutResult:
    """Outcome of a branch checkout or creation operation."""

    success: bool
    branch_name: str
    created: bool
    error: str = ""


class RepoManager:
    """Clone, update, and branch-manage local copies of remote repositories.

    Args:
        workspace_root: Directory under which all managed repos are stored.
            Created automatically if it does not exist.
    """

    def __init__(self, workspace_root: str | Path = "workspace") -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.workspace_root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def local_path(self, repo_name: str) -> Path:
        """Return the expected local path for ``repo_name`` (``owner/name``)."""
        owner, name = self._split(repo_name)
        return self.workspace_root / owner / name

    def clone(
        self,
        repo_name: str,
        clone_url: str | None = None,
        *,
        depth: int | None = None,
    ) -> WorkspaceInfo:
        """Clone ``repo_name`` into the managed workspace.

        If the repository is already cloned, this is a no-op and the existing
        workspace info is returned.  Use :meth:`pull` to update an existing
        clone.

        Args:
            repo_name: Full GitHub repo name, e.g. ``"owner/repo"``.
            clone_url: HTTPS or SSH URL to clone from.  Inferred from
                ``repo_name`` as ``https://github.com/<repo_name>.git``
                when omitted.
            depth: Optional shallow-clone depth.

        Returns:
            :class:`WorkspaceInfo` for the cloned repository.
        """
        path = self.local_path(repo_name)

        if path.exists():
            logger.info("REPO_MANAGER_CLONE_SKIP already exists at %s", path)
            return self._workspace_info(repo_name, path, freshly_cloned=False)

        url = clone_url or f"https://github.com/{repo_name}.git"
        path.parent.mkdir(parents=True, exist_ok=True)

        logger.info("REPO_MANAGER_CLONE_START %s -> %s", url, path)
        kwargs: dict = {}
        if depth is not None:
            kwargs["depth"] = depth
        repo = Repo.clone_from(url, str(path), **kwargs)
        repo.close()
        logger.info("REPO_MANAGER_CLONE_COMPLETE %s", path)

        return self._workspace_info(repo_name, path, freshly_cloned=True)

    def pull(self, repo_name: str) -> WorkspaceInfo:
        """Fast-forward the default remote branch of an existing clone.

        Args:
            repo_name: Full GitHub repo name, e.g. ``"owner/repo"``.

        Returns:
            Updated :class:`WorkspaceInfo`.

        Raises:
            ValueError: If the repository has not been cloned yet.
        """
        path = self.local_path(repo_name)
        if not path.exists():
            raise ValueError(
                f"Repository {repo_name!r} not found at {path}. "
                "Call clone() first."
            )

        logger.info("REPO_MANAGER_PULL_START %s", path)
        repo = Repo(str(path))
        try:
            origin = repo.remotes["origin"]
            origin.pull()
            logger.info("REPO_MANAGER_PULL_COMPLETE %s", path)
        finally:
            repo.close()

        return self._workspace_info(repo_name, path, freshly_cloned=False)

    def checkout_branch(
        self,
        repo_name: str,
        branch_name: str,
        *,
        create: bool = False,
    ) -> BranchCheckoutResult:
        """Switch to (or create) a local branch in the managed clone.

        Args:
            repo_name: Full GitHub repo name.
            branch_name: Name of the branch to check out.
            create: When ``True``, create the branch if it does not exist.

        Returns:
            :class:`BranchCheckoutResult`.
        """
        path = self.local_path(repo_name)
        if not path.exists():
            return BranchCheckoutResult(
                success=False,
                branch_name=branch_name,
                created=False,
                error=f"Repository not found at {path}",
            )

        try:
            repo = Repo(str(path))
            try:
                existing = [h.name for h in repo.heads]
                if branch_name in existing:
                    repo.heads[branch_name].checkout()
                    logger.info(
                        "REPO_MANAGER_CHECKOUT %s branch=%s (existing)",
                        repo_name,
                        branch_name,
                    )
                    return BranchCheckoutResult(
                        success=True, branch_name=branch_name, created=False
                    )

                if not create:
                    return BranchCheckoutResult(
                        success=False,
                        branch_name=branch_name,
                        created=False,
                        error=f"Branch {branch_name!r} does not exist. Pass create=True to create it.",
                    )

                new_branch = repo.create_head(branch_name)
                new_branch.checkout()
                logger.info(
                    "REPO_MANAGER_BRANCH_CREATED %s branch=%s",
                    repo_name,
                    branch_name,
                )
                return BranchCheckoutResult(
                    success=True, branch_name=branch_name, created=True
                )
            finally:
                repo.close()

        except Exception as exc:  # noqa: BLE001
            return BranchCheckoutResult(
                success=False,
                branch_name=branch_name,
                created=False,
                error=str(exc),
            )

    def ensure_workspace(
        self,
        repo_name: str,
        clone_url: str | None = None,
        branch_name: str | None = None,
        *,
        create_branch: bool = True,
    ) -> WorkspaceInfo:
        """Clone-or-pull a repo and optionally check out a branch.

        This is the primary convenience method for setting up a working
        directory before running the issue resolver.  It:

        1. Clones the repo if not yet present, otherwise pulls latest.
        2. If ``branch_name`` is provided, checks out / creates that branch.

        Args:
            repo_name: Full GitHub repo name, e.g. ``"owner/repo"``.
            clone_url: Optional explicit clone URL.
            branch_name: Branch to check out after clone/pull.
            create_branch: Whether to create the branch when it doesn't exist.

        Returns:
            :class:`WorkspaceInfo` describing the ready workspace.
        """
        path = self.local_path(repo_name)
        if path.exists():
            info = self.pull(repo_name)
        else:
            info = self.clone(repo_name, clone_url=clone_url)

        if branch_name:
            self.checkout_branch(repo_name, branch_name, create=create_branch)
            # Refresh info with new branch name
            info = self._workspace_info(repo_name, path, freshly_cloned=info.freshly_cloned)

        return info

    def list_workspaces(self) -> list[WorkspaceInfo]:
        """Return :class:`WorkspaceInfo` for every managed local clone.

        Returns:
            List of workspace info objects, one per cloned repository.
        """
        results: list[WorkspaceInfo] = []
        for owner_dir in self.workspace_root.iterdir():
            if not owner_dir.is_dir():
                continue
            for repo_dir in owner_dir.iterdir():
                if not repo_dir.is_dir():
                    continue
                repo_name = f"{owner_dir.name}/{repo_dir.name}"
                try:
                    results.append(
                        self._workspace_info(repo_name, repo_dir, freshly_cloned=False)
                    )
                except InvalidGitRepositoryError:
                    pass  # skip non-git directories
        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _split(repo_name: str) -> tuple[str, str]:
        """Split ``owner/name`` into a ``(owner, name)`` tuple."""
        parts = repo_name.split("/", 1)
        if len(parts) != 2 or not all(parts):
            raise ValueError(
                f"repo_name must be in 'owner/name' format, got {repo_name!r}"
            )
        return parts[0], parts[1]

    def _workspace_info(
        self, repo_name: str, path: Path, *, freshly_cloned: bool
    ) -> WorkspaceInfo:
        """Build a :class:`WorkspaceInfo` by inspecting the local clone."""
        repo = Repo(str(path))
        try:
            try:
                branch = repo.active_branch.name
            except TypeError:
                branch = repo.head.commit.hexsha[:7]  # detached HEAD
            try:
                sha = repo.head.commit.hexsha
            except ValueError:
                # HEAD points to a branch ref that has no commits yet;
                # fall back to the first available ref if one exists.
                all_refs = list(repo.refs)
                sha = all_refs[0].commit.hexsha if all_refs else ""
        finally:
            repo.close()

        return WorkspaceInfo(
            repo_name=repo_name,
            local_path=path,
            branch=branch,
            commit_sha=sha,
            freshly_cloned=freshly_cloned,
        )
