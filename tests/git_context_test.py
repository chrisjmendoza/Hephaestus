"""Tests for GitContext: status, diff, and auto-commit."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path


def _init_repo(tmpdir: Path) -> "git.Repo":
    """Create a minimal git repo with one initial commit."""
    import git

    repo = git.Repo.init(str(tmpdir))
    repo.config_writer().set_value("user", "name", "Hephaestus Test").release()
    repo.config_writer().set_value("user", "email", "test@hephaestus.local").release()

    initial = tmpdir / "readme.txt"
    initial.write_text("initial\n", encoding="utf-8")
    repo.index.add(["readme.txt"])
    repo.index.commit("initial commit")
    return repo


def main() -> None:
    """Test GitContext status, diff, and commit_patch via GitContext and agent."""
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from agent.git_context import GitContext

    # --- status: clean repo ---
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        root = Path(tmpdir)
        repo = _init_repo(root)

        ctx = GitContext(root)
        status = ctx.status()

        assert status.branch != "", "branch should not be empty"
        assert status.is_dirty is False, "fresh repo should be clean"
        assert status.staged_files == []
        assert status.unstaged_files == []
        assert status.commit_sha != ""
        assert "initial" in status.commit_message

        ctx.repo.close()
        repo.close()

    # --- status: dirty after file change ---
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        root = Path(tmpdir)
        repo = _init_repo(root)
        (root / "readme.txt").write_text("modified\n", encoding="utf-8")

        ctx = GitContext(root)
        status = ctx.status()
        assert status.is_dirty is True
        assert "readme.txt" in status.unstaged_files

        ctx.repo.close()
        repo.close()

    # --- status: untracked file ---
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        root = Path(tmpdir)
        repo = _init_repo(root)
        (root / "new_file.py").write_text("x = 1\n", encoding="utf-8")

        ctx = GitContext(root)
        status = ctx.status()
        assert status.is_dirty is True
        assert "new_file.py" in status.untracked_files

        ctx.repo.close()
        repo.close()

    # --- diff_working_tree: shows change ---
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        root = Path(tmpdir)
        repo = _init_repo(root)
        (root / "readme.txt").write_text("changed content\n", encoding="utf-8")

        ctx = GitContext(root)
        diff = ctx.diff_working_tree()
        assert "changed content" in diff or "-initial" in diff or diff != "", (
            "diff should contain change info"
        )

        ctx.repo.close()
        repo.close()

    # --- commit_patch: stages and commits files ---
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        root = Path(tmpdir)
        repo = _init_repo(root)

        new_file = root / "feature.py"
        new_file.write_text("def feature(): pass\n", encoding="utf-8")

        ctx = GitContext(root)
        result = ctx.commit_patch(["feature.py"], "add feature.py")

        assert result.committed is True
        assert result.commit_sha != ""
        assert "feature.py" in result.files_committed
        assert repo.head.commit.message.strip() == "add feature.py"

        ctx.repo.close()
        repo.close()

    # --- commit_patch: ValueError on empty file list ---
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        root = Path(tmpdir)
        repo = _init_repo(root)
        ctx = GitContext(root)
        try:
            ctx.commit_patch([], "empty commit")
            assert False, "Expected ValueError for empty file_paths"
        except ValueError:
            pass
        ctx.repo.close()
        repo.close()

    # --- Agent integration: git_status and git_commit_patch log lifecycle events ---
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        parent = Path(tmpdir)
        root = parent / "repo"
        root.mkdir()
        repo = _init_repo(root)

        from agent.agent import HephaestusAgent

        # Keep log outside the git repo so it doesn't pollute the working tree
        log_path = parent / "test.log"
        agent = HephaestusAgent(log_path=str(log_path))

        status = agent.git_status(str(root))
        assert status.is_dirty is False

        log = log_path.read_text(encoding="utf-8")
        assert "GIT_STATUS_START" in log
        assert "GIT_STATUS_COMPLETE" in log

        # Write a new file and commit via agent
        patch_file = root / "patch.py"
        patch_file.write_text("x = 42\n", encoding="utf-8")
        commit_result = agent.git_commit_patch(
            ["patch.py"], "agent: add patch.py", repo_path=str(root)
        )
        assert commit_result.committed is True
        log2 = log_path.read_text(encoding="utf-8")
        assert "GIT_COMMIT_START" in log2
        assert "GIT_COMMIT_COMPLETE" in log2

        if agent._git:
            agent._git.repo.close()
        repo.close()

    print("PASS")
    print("Git context test passed")


if __name__ == "__main__":
    main()
