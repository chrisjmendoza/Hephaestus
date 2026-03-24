"""Tests for TaskReporter structured report generation and persistence."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


def main() -> None:
    """Test TaskReport build, record, persist, text rendering, and agent integration."""
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from agent.task_report import TaskReporter

    # --- start creates an in-progress report ---
    reporter = TaskReporter()
    plan = ["Analyze repo", "Apply patch", "Run tests"]
    report = reporter.start("add logging to foo.py", plan)

    assert report.task == "add logging to foo.py"
    assert report.plan == plan
    assert report.outcome == "in_progress"
    assert report.started_at != ""
    assert report.completed_at == ""
    assert report.patches == []
    assert report.test_runs == []
    assert report.commits == []

    # --- record_patch ---
    reporter.record_patch(report, "foo.py", "--- a\n+++ b\n", applied=True, dry_run=False)
    assert len(report.patches) == 1
    assert report.patches[0].file_path == "foo.py"
    assert report.patches[0].applied is True

    # --- record_test ---
    reporter.record_test(report, "tests/", passed=True, summary="3 passed", failed_tests=[])
    assert len(report.test_runs) == 1
    assert report.test_runs[0].passed is True

    # --- record_commit ---
    reporter.record_commit(report, "abc1234", "add logging", ["foo.py"])
    assert len(report.commits) == 1
    assert report.commits[0].commit_sha == "abc1234"

    # --- finish sets outcome and completed_at ---
    reporter.finish(report, outcome="success")
    assert report.outcome == "success"
    assert report.completed_at != ""

    # --- to_dict roundtrip ---
    d = report.to_dict()
    assert d["task"] == "add logging to foo.py"
    assert d["outcome"] == "success"
    assert len(d["patches"]) == 1
    assert len(d["test_runs"]) == 1
    assert len(d["commits"]) == 1

    # --- to_text contains key sections ---
    text = report.to_text()
    assert "Task Report" in text
    assert "add logging to foo.py" in text
    assert "success" in text
    assert "foo.py" in text
    assert "3 passed" in text
    assert "abc1234" in text

    # --- persist and load ---
    with tempfile.TemporaryDirectory() as tmpdir:
        report_path = Path(tmpdir) / "task_report.json"
        reporter2 = TaskReporter(report_path=report_path)

        r2 = reporter2.start("task B", ["step 1"])
        reporter2.finish(r2, outcome="success")
        reporter2.persist(r2)

        assert report_path.exists()
        loaded = reporter2.load()
        assert loaded["task"] == "task B"
        assert loaded["outcome"] == "success"

    # --- load raises FileNotFoundError if no report exists ---
    with tempfile.TemporaryDirectory() as tmpdir:
        reporter3 = TaskReporter(report_path=Path(tmpdir) / "missing.json")
        try:
            reporter3.load()
            assert False, "Expected FileNotFoundError"
        except FileNotFoundError:
            pass

    # --- Agent integration: generate_report persists and logs events ---
    with tempfile.TemporaryDirectory() as tmpdir:
        from agent.agent import HephaestusAgent
        from agent.patch_executor import PatchResult
        from agent.test_runner import TestRunResult
        from agent.git_context import GitCommitResult

        report_path = Path(tmpdir) / "task_report.json"
        log_path = Path(tmpdir) / "agent.log"
        agent = HephaestusAgent(log_path=str(log_path))
        agent.task_reporter = TaskReporter(report_path=report_path)

        patch_res = PatchResult(
            file_path="bar.py",
            diff="--- a\n+++ b\n",
            applied=True,
            dry_run=False,
        )
        test_res = TestRunResult(
            command=["python", "tests/"],
            exit_code=0,
            stdout="PASS\n",
            stderr="",
            passed=True,
            summary="2 passed",
            failed_tests=[],
        )
        commit_res = GitCommitResult(
            committed=True,
            commit_sha="deadbeef",
            commit_message="agent: patch bar.py",
            files_committed=["bar.py"],
        )

        report = agent.generate_report(
            task="patch bar.py",
            plan=["step A", "step B"],
            patch_results=[patch_res],
            test_results=[test_res],
            commit_results=[commit_res],
            outcome="success",
        )

        assert report.outcome == "success"
        assert len(report.patches) == 1
        assert len(report.test_runs) == 1
        assert len(report.commits) == 1
        assert report_path.exists()

        raw = json.loads(report_path.read_text(encoding="utf-8"))
        assert raw["task"] == "patch bar.py"

        log = log_path.read_text(encoding="utf-8")
        assert "TASK_REPORT_START" in log
        assert "TASK_REPORT_COMPLETE" in log

    print("PASS")
    print("Task report test passed")


if __name__ == "__main__":
    main()
