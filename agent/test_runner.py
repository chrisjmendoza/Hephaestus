"""Test runner integration for Hephaestus."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TestRunResult:
    """Structured outcome of a test run."""

    command: list[str]
    exit_code: int
    stdout: str
    stderr: str
    passed: bool
    summary: str
    failed_tests: list[str] = field(default_factory=list)


class TestRunner:
    """Discovers and runs project tests, returning structured pass/fail results."""

    _PYTEST_INDICATORS = ("PASSED", "FAILED", "ERROR", "passed", "failed", "error")

    def run(
        self,
        test_path: str | Path = ".",
        extra_args: list[str] | None = None,
        timeout: int = 120,
    ) -> TestRunResult:
        """Run pytest against test_path and return a structured result.

        Falls back to running each test/*.py file directly when pytest is not
        installed, so the agent remains functional without pytest on the path.

        Args:
            test_path: File or directory to pass to pytest.
            extra_args: Additional arguments forwarded to pytest.
            timeout: Max seconds to allow the process to run.

        Returns:
            TestRunResult with exit code, output, and parsed failure list.
        """
        path = Path(test_path)
        cmd = [sys.executable, "-m", "pytest", str(path), "-v", "--tb=short"]
        if extra_args:
            cmd.extend(extra_args)

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        # If pytest is not found, fall back to direct execution of test files
        if proc.returncode == 5 or "No module named pytest" in proc.stderr:
            return self._run_direct(path, timeout=timeout)

        return self._parse_pytest_output(cmd, proc)

    def run_file(
        self,
        test_file: str | Path,
        timeout: int = 60,
    ) -> TestRunResult:
        """Run a single Hephaestus-style test file directly (via python <file>).

        Args:
            test_file: Path to a test module with a `main()` entry point.
            timeout: Max seconds to allow the process to run.

        Returns:
            TestRunResult with exit code, output, and pass/fail status.
        """
        path = Path(test_file)
        cmd = [sys.executable, str(path)]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        passed = proc.returncode == 0
        summary = f"{'PASS' if passed else 'FAIL'}: {path.name}"
        failed: list[str] = [] if passed else [path.name]
        return TestRunResult(
            command=cmd,
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            passed=passed,
            summary=summary,
            failed_tests=failed,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_direct(self, path: Path, timeout: int) -> TestRunResult:
        """Run all *_test.py files in path directly when pytest is unavailable."""
        test_files = list(path.rglob("*_test.py")) if path.is_dir() else [path]
        all_pass = True
        outputs: list[str] = []
        failed: list[str] = []
        cmd: list[str] = [sys.executable, "<direct>"]

        for tf in test_files:
            result = self.run_file(tf, timeout=timeout)
            outputs.append(result.stdout + result.stderr)
            if not result.passed:
                all_pass = False
                failed.append(tf.name)

        summary = self._build_summary(len(test_files), len(failed))
        return TestRunResult(
            command=cmd,
            exit_code=0 if all_pass else 1,
            stdout="\n".join(outputs),
            stderr="",
            passed=all_pass,
            summary=summary,
            failed_tests=failed,
        )

    def _parse_pytest_output(
        self,
        cmd: list[str],
        proc: subprocess.CompletedProcess,
    ) -> TestRunResult:
        """Extract pass/fail counts and failed test names from pytest output."""
        passed = proc.returncode == 0
        failed_tests: list[str] = []

        for line in proc.stdout.splitlines():
            if " FAILED" in line:
                # e.g. "tests/foo_test.py::test_bar FAILED"
                failed_tests.append(line.split(" FAILED")[0].strip())

        summary = self._extract_pytest_summary(proc.stdout) or (
            "PASS" if passed else f"FAIL ({len(failed_tests)} failures)"
        )

        return TestRunResult(
            command=cmd,
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            passed=passed,
            summary=summary,
            failed_tests=failed_tests,
        )

    @staticmethod
    def _extract_pytest_summary(output: str) -> str:
        """Return the last summary line from pytest output (e.g. '3 passed in 0.4s')."""
        for line in reversed(output.splitlines()):
            stripped = line.strip()
            if stripped.startswith("=") and ("passed" in stripped or "failed" in stripped or "error" in stripped):
                return stripped.strip("= ").strip()
        return ""

    @staticmethod
    def _build_summary(total: int, failed_count: int) -> str:
        passed_count = total - failed_count
        if failed_count == 0:
            return f"{passed_count} passed"
        return f"{passed_count} passed, {failed_count} failed"
