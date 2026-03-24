"""Structured task reporting for Hephaestus."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class PatchEntry:
    """Record of a single file patch applied during a task."""

    file_path: str
    diff: str
    dry_run: bool
    applied: bool


@dataclass
class TestEntry:
    """Record of a test run performed during a task."""

    test_path: str
    passed: bool
    summary: str
    failed_tests: list[str]


@dataclass
class CommitEntry:
    """Record of a git commit made during a task."""

    commit_sha: str
    commit_message: str
    files_committed: list[str]


@dataclass
class TaskReport:
    """Full structured record of a completed agent task."""

    task: str
    plan: list[str]
    patches: list[PatchEntry] = field(default_factory=list)
    test_runs: list[TestEntry] = field(default_factory=list)
    commits: list[CommitEntry] = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: str = ""
    outcome: str = "in_progress"

    def to_dict(self) -> dict:
        """Serialize the report to a JSON-compatible dict."""
        return {
            "task": self.task,
            "plan": self.plan,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "outcome": self.outcome,
            "patches": [
                {
                    "file_path": p.file_path,
                    "applied": p.applied,
                    "dry_run": p.dry_run,
                    "diff": p.diff,
                }
                for p in self.patches
            ],
            "test_runs": [
                {
                    "test_path": t.test_path,
                    "passed": t.passed,
                    "summary": t.summary,
                    "failed_tests": t.failed_tests,
                }
                for t in self.test_runs
            ],
            "commits": [
                {
                    "commit_sha": c.commit_sha,
                    "commit_message": c.commit_message,
                    "files_committed": c.files_committed,
                }
                for c in self.commits
            ],
        }

    def to_text(self) -> str:
        """Render a human-readable summary of the report."""
        lines: list[str] = [
            f"Task Report",
            f"===========",
            f"Task:      {self.task}",
            f"Outcome:   {self.outcome}",
            f"Started:   {self.started_at}",
            f"Completed: {self.completed_at or '—'}",
            "",
            "Plan:",
        ]
        for i, step in enumerate(self.plan, 1):
            lines.append(f"  {i}. {step}")

        if self.patches:
            lines.append("")
            lines.append(f"Patches ({len(self.patches)}):")
            for p in self.patches:
                status = "applied" if p.applied else ("dry-run" if p.dry_run else "skipped")
                lines.append(f"  [{status}] {p.file_path}")

        if self.test_runs:
            lines.append("")
            lines.append(f"Test Runs ({len(self.test_runs)}):")
            for t in self.test_runs:
                icon = "PASS" if t.passed else "FAIL"
                lines.append(f"  [{icon}] {t.test_path} — {t.summary}")
                for failed in t.failed_tests:
                    lines.append(f"         ✗ {failed}")

        if self.commits:
            lines.append("")
            lines.append(f"Commits ({len(self.commits)}):")
            for c in self.commits:
                lines.append(f"  [{c.commit_sha}] {c.commit_message}")
                for f in c.files_committed:
                    lines.append(f"         • {f}")

        return "\n".join(lines)


class TaskReporter:
    """Builds, persists, and retrieves structured task reports."""

    def __init__(
        self,
        report_path: str | Path = "memory/task_report.json",
    ) -> None:
        """Initialize with path for persisted report storage."""
        self.report_path = Path(report_path)

    def start(self, task: str, plan: list[str]) -> TaskReport:
        """Create and return a new in-progress TaskReport."""
        return TaskReport(task=task, plan=plan)

    def record_patch(
        self,
        report: TaskReport,
        file_path: str,
        diff: str,
        applied: bool,
        dry_run: bool,
    ) -> None:
        """Append a patch entry to the report."""
        report.patches.append(
            PatchEntry(file_path=file_path, diff=diff, applied=applied, dry_run=dry_run)
        )

    def record_test(
        self,
        report: TaskReport,
        test_path: str,
        passed: bool,
        summary: str,
        failed_tests: list[str],
    ) -> None:
        """Append a test run entry to the report."""
        report.test_runs.append(
            TestEntry(
                test_path=test_path,
                passed=passed,
                summary=summary,
                failed_tests=failed_tests,
            )
        )

    def record_commit(
        self,
        report: TaskReport,
        commit_sha: str,
        commit_message: str,
        files_committed: list[str],
    ) -> None:
        """Append a commit entry to the report."""
        report.commits.append(
            CommitEntry(
                commit_sha=commit_sha,
                commit_message=commit_message,
                files_committed=files_committed,
            )
        )

    def finish(self, report: TaskReport, outcome: str = "success") -> TaskReport:
        """Mark the report complete with a final outcome and return it."""
        report.completed_at = datetime.now().isoformat()
        report.outcome = outcome
        return report

    def persist(self, report: TaskReport) -> None:
        """Write the report to disk as JSON."""
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        self.report_path.write_text(
            json.dumps(report.to_dict(), indent=2), encoding="utf-8"
        )

    def load(self) -> dict:
        """Load and return the last persisted report as a dict."""
        if not self.report_path.exists():
            raise FileNotFoundError(
                f"No task report found at {self.report_path}."
            )
        return json.loads(self.report_path.read_text(encoding="utf-8"))
