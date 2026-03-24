"""Tests for PatchExecutor file patching with dry-run support."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path


def main() -> None:
    """Test PatchExecutor apply, apply_replacement, dry-run, and error cases."""
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from agent.patch_executor import PatchExecutor

    executor = PatchExecutor()

    # --- Full content replacement ---
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "test_file.py"
        target.write_text("original content\n", encoding="utf-8")

        # Dry-run must not mutate the file
        result = executor.apply(target, "new content\n", dry_run=True)
        assert result.dry_run is True
        assert result.applied is False
        assert "-original content" in result.diff
        assert "+new content" in result.diff
        assert target.read_text(encoding="utf-8") == "original content\n", (
            "Dry-run must not write to disk"
        )

        # Live run must write
        result = executor.apply(target, "new content\n", dry_run=False)
        assert result.applied is True
        assert result.dry_run is False
        assert target.read_text(encoding="utf-8") == "new content\n"

    # --- Substring replacement ---
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "sample.py"
        target.write_text("def foo():\n    pass\n", encoding="utf-8")

        result = executor.apply_replacement(
            target, "    pass\n", "    return 42\n", dry_run=False
        )
        assert result.applied is True
        assert "return 42" in target.read_text(encoding="utf-8")
        assert "-    pass" in result.diff
        assert "+    return 42" in result.diff

    # --- Dry-run replacement must not write ---
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "dry.py"
        target.write_text("x = 1\n", encoding="utf-8")

        result = executor.apply_replacement(target, "x = 1\n", "x = 99\n", dry_run=True)
        assert result.applied is False
        assert target.read_text(encoding="utf-8") == "x = 1\n", (
            "Dry-run replacement must not write to disk"
        )

    # --- Missing old_text raises ValueError ---
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "x.py"
        target.write_text("some code\n", encoding="utf-8")
        try:
            executor.apply_replacement(target, "not present", "replacement")
            assert False, "Expected ValueError for missing old_text"
        except ValueError:
            pass

    # --- Ambiguous old_text raises ValueError ---
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "ambiguous.py"
        target.write_text("x = 1\nx = 1\n", encoding="utf-8")
        try:
            executor.apply_replacement(target, "x = 1\n", "x = 2\n")
            assert False, "Expected ValueError for ambiguous old_text"
        except ValueError:
            pass

    # --- Agent integration: apply_patch and apply_replacement via agent ---
    with tempfile.TemporaryDirectory() as tmpdir:
        from agent.agent import HephaestusAgent

        log_path = Path(tmpdir) / "test.log"
        agent = HephaestusAgent(log_path=str(log_path))

        target = Path(tmpdir) / "agent_target.py"
        target.write_text("a = 1\n", encoding="utf-8")

        patch_result = agent.apply_patch(str(target), "a = 2\n", dry_run=False)
        assert patch_result.applied is True
        assert target.read_text(encoding="utf-8") == "a = 2\n"

        log_contents = log_path.read_text(encoding="utf-8")
        assert "PATCH_START" in log_contents
        assert "PATCH_PREVIEW" in log_contents
        assert "PATCH_APPLIED" in log_contents

        repl_result = agent.apply_replacement(str(target), "a = 2\n", "a = 3\n", dry_run=True)
        assert repl_result.applied is False
        assert "PATCH_SKIPPED" in log_path.read_text(encoding="utf-8")

    print("PASS")
    print("Patch executor test passed")


if __name__ == "__main__":
    main()
