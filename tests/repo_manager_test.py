"""Tests for RepoManager: clone, pull, checkout, ensure_workspace, list."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, call, patch


def _make_bare_remote(tmpdir: Path) -> tuple[Path, "git.Repo"]:
    """Create a bare git repo acting as the remote, return (path, repo)."""
    import git

    remote_path = tmpdir / "remote.git"
    remote_path.mkdir()
    remote = git.Repo.init(str(remote_path), bare=True)
    return remote_path, remote


def _seed_remote(bare_path: Path) -> None:
    """Push an initial commit into the bare repo via a temp clone."""
    import git

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as seed_dir:
        seed = git.Repo.clone_from(str(bare_path), seed_dir)
        seed.config_writer().set_value("user", "name", "Hephaestus Test").release()
        seed.config_writer().set_value("user", "email", "test@hephaestus.local").release()
        (Path(seed_dir) / "README.md").write_text("# hello\n", encoding="utf-8")
        seed.index.add(["README.md"])
        seed.index.commit("initial commit")
        seed.remotes["origin"].push("HEAD:main")
        seed.close()

    # Point the bare repo's HEAD at main so clones check out the right branch
    bare = git.Repo(str(bare_path))
    bare.head.reference = bare.refs["main"]
    bare.close()


def main() -> None:
    """Run all RepoManager tests."""
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from agent.repo_manager import RepoManager

    # ------------------------------------------------------------------ #
    print("Test 1: clone() creates workspace and returns WorkspaceInfo")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        root = Path(tmpdir)
        remote_path, remote = _make_bare_remote(root)
        _seed_remote(remote_path)

        workspace = root / "ws"
        mgr = RepoManager(workspace_root=workspace)
        info = mgr.clone("owner/repo", clone_url=str(remote_path))

        assert info.repo_name == "owner/repo"
        assert info.freshly_cloned is True
        assert info.local_path.exists()
        assert info.commit_sha != ""
        assert (info.local_path / "README.md").exists()
        remote.close()
    print("  PASS")

    # ------------------------------------------------------------------ #
    print("Test 2: clone() on existing path is a no-op (freshly_cloned=False)")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        root = Path(tmpdir)
        remote_path, remote = _make_bare_remote(root)
        _seed_remote(remote_path)

        workspace = root / "ws"
        mgr = RepoManager(workspace_root=workspace)
        mgr.clone("owner/repo", clone_url=str(remote_path))
        info2 = mgr.clone("owner/repo", clone_url=str(remote_path))

        assert info2.freshly_cloned is False
        remote.close()
    print("  PASS")

    # ------------------------------------------------------------------ #
    print("Test 3: pull() updates an existing clone")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        root = Path(tmpdir)
        remote_path, remote = _make_bare_remote(root)
        _seed_remote(remote_path)

        workspace = root / "ws"
        mgr = RepoManager(workspace_root=workspace)
        mgr.clone("owner/repo", clone_url=str(remote_path))
        info = mgr.pull("owner/repo")

        assert info.commit_sha != ""
        assert info.freshly_cloned is False
        remote.close()
    print("  PASS")

    # ------------------------------------------------------------------ #
    print("Test 4: pull() raises ValueError when repo not cloned yet")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        mgr = RepoManager(workspace_root=Path(tmpdir) / "ws")
        raised = False
        try:
            mgr.pull("owner/nope")
        except ValueError:
            raised = True
        assert raised, "Expected ValueError for uncloned repo"
    print("  PASS")

    # ------------------------------------------------------------------ #
    print("Test 5: checkout_branch() creates a new branch")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        root = Path(tmpdir)
        remote_path, remote = _make_bare_remote(root)
        _seed_remote(remote_path)

        workspace = root / "ws"
        mgr = RepoManager(workspace_root=workspace)
        mgr.clone("owner/repo", clone_url=str(remote_path))

        result = mgr.checkout_branch("owner/repo", "hephaestus/fix-1", create=True)
        assert result.success is True
        assert result.created is True
        assert result.branch_name == "hephaestus/fix-1"
        remote.close()
    print("  PASS")

    # ------------------------------------------------------------------ #
    print("Test 6: checkout_branch() existing branch without create=True")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        root = Path(tmpdir)
        remote_path, remote = _make_bare_remote(root)
        _seed_remote(remote_path)

        workspace = root / "ws"
        mgr = RepoManager(workspace_root=workspace)
        mgr.clone("owner/repo", clone_url=str(remote_path))
        mgr.checkout_branch("owner/repo", "existing", create=True)

        result = mgr.checkout_branch("owner/repo", "existing", create=False)
        assert result.success is True
        assert result.created is False
        remote.close()
    print("  PASS")

    # ------------------------------------------------------------------ #
    print("Test 7: checkout_branch() returns error when branch missing and create=False")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        root = Path(tmpdir)
        remote_path, remote = _make_bare_remote(root)
        _seed_remote(remote_path)

        workspace = root / "ws"
        mgr = RepoManager(workspace_root=workspace)
        mgr.clone("owner/repo", clone_url=str(remote_path))

        result = mgr.checkout_branch("owner/repo", "nonexistent", create=False)
        assert result.success is False
        assert result.error != ""
        remote.close()
    print("  PASS")

    # ------------------------------------------------------------------ #
    print("Test 8: ensure_workspace() clones fresh and checks out branch")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        root = Path(tmpdir)
        remote_path, remote = _make_bare_remote(root)
        _seed_remote(remote_path)

        workspace = root / "ws"
        mgr = RepoManager(workspace_root=workspace)
        info = mgr.ensure_workspace(
            "owner/repo",
            clone_url=str(remote_path),
            branch_name="hephaestus/task-99",
            create_branch=True,
        )

        assert info.local_path.exists()
        assert info.branch == "hephaestus/task-99"
        remote.close()
    print("  PASS")

    # ------------------------------------------------------------------ #
    print("Test 9: list_workspaces() returns one entry after a clone")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        root = Path(tmpdir)
        remote_path, remote = _make_bare_remote(root)
        _seed_remote(remote_path)

        workspace = root / "ws"
        mgr = RepoManager(workspace_root=workspace)
        mgr.clone("owner/repo", clone_url=str(remote_path))

        workspaces = mgr.list_workspaces()
        assert len(workspaces) == 1
        assert workspaces[0].repo_name == "owner/repo"
        remote.close()
    print("  PASS")

    # ------------------------------------------------------------------ #
    print("Test 10: local_path() returns correct path structure")
    mgr = RepoManager(workspace_root="/some/ws")
    p = mgr.local_path("myorg/myrepo")
    assert p.parts[-2:] == ("myorg", "myrepo"), f"unexpected path {p}"
    print("  PASS")

    print("\nAll repo_manager tests passed.")


if __name__ == "__main__":
    main()
