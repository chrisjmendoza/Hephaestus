"""Integration tests for Hephaestus — real file I/O and real git operations.

These tests exercise the full stack from execute_step down to the filesystem and
git layer using a small fixture repository created in a temp directory.  The LLM
layer (task_reasoner) is mocked so the tests are deterministic and do not require
an ANTHROPIC_API_KEY to run.

What is NOT mocked:
- File writes (apply_patch writes to real temp files)
- Git operations (commit_patch creates real commits in a real git.Repo)
- Lifecycle logging (log events written to a real log file)
- Memory recording (MemoryStore persists to a real JSON file in the temp dir)
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import git as gitpython

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from agent.agent import HephaestusAgent


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

CALCULATOR_SOURCE = """\
def add(a, b):
    return a - b  # bug: should be +


def subtract(a, b):
    return a - b
"""

CALCULATOR_FIXED = """\
def add(a, b):
    return a + b  # fixed


def subtract(a, b):
    return a - b
"""

CALCULATOR_TEST = """\
from calculator import add, subtract

def test_add():
    assert add(1, 2) == 3

def test_subtract():
    assert subtract(5, 3) == 2
"""


def _make_fixture_repo(tmp_path: Path) -> gitpython.Repo:
    """Create a minimal git repo with a Python file and one initial commit."""
    repo = gitpython.Repo.init(str(tmp_path))
    # Configure local identity so commits don't fail in CI
    repo.config_writer().set_value("user", "name", "Test").release()
    repo.config_writer().set_value("user", "email", "test@test.local").release()

    calc = tmp_path / "calculator.py"
    calc.write_text(CALCULATOR_SOURCE, encoding="utf-8")

    test_file = tmp_path / "test_calculator.py"
    test_file.write_text(CALCULATOR_TEST, encoding="utf-8")

    repo.index.add(["calculator.py", "test_calculator.py"])
    repo.index.commit("initial commit")
    return repo


def _cleanup(tmp: str) -> None:
    """Remove temp directory, ignoring Windows file-lock errors from gitpython."""
    shutil.rmtree(tmp, ignore_errors=True)


def _make_agent(tmp_path: Path) -> HephaestusAgent:
    """Create an agent with log and memory paths isolated to tmp_path."""
    log_path = tmp_path / "integration.log"
    memory_root = str(tmp_path / "memory")
    agent = HephaestusAgent(log_path=str(log_path))
    # Override memory store to use the temp directory
    from agent.memory_store import MemoryStore
    agent.memory = MemoryStore.for_repo(str(tmp_path), memory_root=memory_root)
    return agent


# ---------------------------------------------------------------------------
# Test 1 — apply_patch writes to a real file
# ---------------------------------------------------------------------------

def test_apply_patch_modifies_real_file():
    tmp = tempfile.mkdtemp()
    try:
        tmp_path = Path(tmp)
        calc = tmp_path / "calculator.py"
        calc.write_text(CALCULATOR_SOURCE, encoding="utf-8")

        agent = _make_agent(tmp_path)
        result = agent.apply_patch(str(calc), CALCULATOR_FIXED)

        assert result.applied, "patch should have been applied"
        assert "+" in result.diff, "diff should show the + change"
        content = calc.read_text(encoding="utf-8")
        assert "return a + b" in content, "file should contain the fixed line"
        assert "return a - b  # bug" not in content, "buggy line should be gone"
    finally:
        _cleanup(tmp)

    print("PASS: apply_patch modifies real file on disk")


# ---------------------------------------------------------------------------
# Test 2 — git_commit_patch creates a real commit
# ---------------------------------------------------------------------------

def test_git_commit_creates_real_commit():
    tmp = tempfile.mkdtemp()
    try:
        tmp_path = Path(tmp)
        repo = _make_fixture_repo(tmp_path)
        initial_sha = repo.head.commit.hexsha

        # Modify the file so there's something to commit
        calc = tmp_path / "calculator.py"
        calc.write_text(CALCULATOR_FIXED, encoding="utf-8")

        agent = _make_agent(tmp_path)
        # Reset lazy _git so it points at our temp repo
        agent._git = None
        commit_result = agent.git_commit_patch(
            [str(calc)], "fix: correct add function", repo_path=str(tmp_path)
        )

        assert commit_result.committed, "commit should succeed"
        assert commit_result.commit_sha, "commit SHA should be non-empty"
        assert repo.head.commit.hexsha != initial_sha, "HEAD should have advanced"
        assert "fix: correct add function" in str(repo.head.commit.message)
        repo.close()
    finally:
        _cleanup(tmp)

    print("PASS: git_commit_patch creates a real git commit")


# ---------------------------------------------------------------------------
# Test 3 — execute_step implement + commit on fixture repo
# ---------------------------------------------------------------------------

def test_execute_step_patch_then_commit_on_fixture_repo():
    tmp = tempfile.mkdtemp()
    try:
        tmp_path = Path(tmp)
        repo = _make_fixture_repo(tmp_path)

        agent = _make_agent(tmp_path)
        agent._git = None  # ensure GitContext uses tmp_path

        # Mock generate_patch to return the fixed content deterministically
        with patch.object(
            agent.task_reasoner, "generate_patch", return_value=CALCULATOR_FIXED
        ):
            patch_output = agent.execute_step(
                "implement fix in calculator.py", repo_path=str(tmp_path)
            )

        assert "Patched calculator.py" in patch_output, f"unexpected output: {patch_output}"
        calc = tmp_path / "calculator.py"
        assert "return a + b" in calc.read_text(encoding="utf-8"), "file should be fixed"

        # Now commit the patched file via execute_step
        commit_output = agent.execute_step(
            "commit the fix to calculator.py", repo_path=str(tmp_path)
        )

        assert "Committed" in commit_output or "sha=" in commit_output, (
            f"unexpected commit output: {commit_output}"
        )
        assert repo.head.commit.hexsha, "HEAD commit should exist"
        repo.close()
    finally:
        _cleanup(tmp)

    print("PASS: execute_step implement + commit on fixture repo")


# ---------------------------------------------------------------------------
# Test 4 — run_task full lifecycle on the Hephaestus repo (analyze only)
# ---------------------------------------------------------------------------

def test_run_task_full_lifecycle():
    """Execute run_task against the Hephaestus repo using a mocked plan.

    This exercises the full agent loop — generate_task_plan → execute_step ×N
    → memory.record() — with analyze-only steps (no file writes) so the test
    leaves no side effects on the working repo.
    """
    tmp = tempfile.mkdtemp()
    try:
        log_path = Path(tmp) / "lifecycle.log"
        memory_path = Path(tmp) / "memory"

        agent = HephaestusAgent(log_path=str(log_path))
        from agent.memory_store import MemoryStore
        agent.memory = MemoryStore.for_repo(str(project_root), memory_root=str(memory_path))

        analyze_steps = [
            "analyze the repository structure",
            "review test coverage",
        ]

        with patch.object(agent, "generate_task_plan", return_value=analyze_steps):
            with patch.object(agent, "semantic_search", return_value=["agent/agent.py", "main.py"]):
                output = agent.run_task("Audit repository structure")

        # Lifecycle output assertions
        assert "Hephaestus initialized" in output
        assert "Plan generated:" in output
        assert "Task complete" in output

        # Log assertions
        log_text = log_path.read_text(encoding="utf-8")
        for event in ("TASK_RECEIVED", "PLAN_CREATED", "STEP_START", "STEP_COMPLETE", "TASK_COMPLETE"):
            assert event in log_text, f"Missing lifecycle event: {event}"
        assert "MEMORY_RECORDED" in log_text

        # Memory assertions
        records = agent.memory.recent(n=10)
        assert len(records) >= 1
        assert records[-1].task == "Audit repository structure"
    finally:
        _cleanup(tmp)

    print("PASS: run_task full lifecycle — all events logged, memory recorded")


# ---------------------------------------------------------------------------
# Test 5 — dry_run=True prevents file writes in execute_step
# ---------------------------------------------------------------------------

def test_integration_dry_run_no_file_changes():
    """Verify that dry-run mode does not modify files in a fixture repo."""
    tmp = tempfile.mkdtemp()
    try:
        tmp_path = Path(tmp)
        _make_fixture_repo(tmp_path)

        calc = tmp_path / "calculator.py"
        original = calc.read_text(encoding="utf-8")

        agent = _make_agent(tmp_path)
        with patch.object(agent.task_reasoner, "generate_patch", return_value=CALCULATOR_FIXED):
            result = agent.execute_step(
                "implement fix in calculator.py", repo_path=str(tmp_path), dry_run=True
            )

        assert "[dry-run]" in result, f"expected dry-run marker, got: {result}"
        assert calc.read_text(encoding="utf-8") == original, "file must not change in dry-run"
    finally:
        _cleanup(tmp)

    print("PASS: dry-run prevents file writes in fixture repo")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_apply_patch_modifies_real_file()
    test_git_commit_creates_real_commit()
    test_execute_step_patch_then_commit_on_fixture_repo()
    test_run_task_full_lifecycle()
    test_integration_dry_run_no_file_changes()
    print("\n=== integration tests PASSED ===")
