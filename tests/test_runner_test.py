"""Tests for TestRunner structured pass/fail execution."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path


def main() -> None:
    """Test TestRunner.run_file, pass/fail detection, and agent integration."""
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from agent.test_runner import TestRunner

    runner = TestRunner()

    # --- run_file: passing test ---
    with tempfile.TemporaryDirectory() as tmpdir:
        passing = Path(tmpdir) / "passing_test.py"
        passing.write_text(
            "def main():\n    print('PASS')\n\nif __name__ == '__main__':\n    main()\n",
            encoding="utf-8",
        )
        result = runner.run_file(passing)
        assert result.passed is True, "Passing test should report passed=True"
        assert result.exit_code == 0
        assert "PASS" in result.stdout

    # --- run_file: failing test ---
    with tempfile.TemporaryDirectory() as tmpdir:
        failing = Path(tmpdir) / "failing_test.py"
        failing.write_text(
            "def main():\n    raise AssertionError('intentional failure')\n\n"
            "if __name__ == '__main__':\n    main()\n",
            encoding="utf-8",
        )
        result = runner.run_file(failing)
        assert result.passed is False, "Failing test should report passed=False"
        assert result.exit_code != 0
        assert failing.name in result.failed_tests

    # --- run: run all test files in a directory ---
    with tempfile.TemporaryDirectory() as tmpdir:
        t1 = Path(tmpdir) / "alpha_test.py"
        t2 = Path(tmpdir) / "beta_test.py"
        t1.write_text(
            "def main():\n    print('PASS')\n\nif __name__ == '__main__':\n    main()\n",
            encoding="utf-8",
        )
        t2.write_text(
            "def main():\n    print('PASS')\n\nif __name__ == '__main__':\n    main()\n",
            encoding="utf-8",
        )
        result = runner.run(tmpdir)
        assert result.passed is True
        assert result.failed_tests == []

    # --- run: mixed pass/fail directory ---
    with tempfile.TemporaryDirectory() as tmpdir:
        good = Path(tmpdir) / "good_test.py"
        bad = Path(tmpdir) / "bad_test.py"
        good.write_text(
            "def main():\n    print('PASS')\n\nif __name__ == '__main__':\n    main()\n",
            encoding="utf-8",
        )
        bad.write_text(
            "import sys\ndef main():\n    sys.exit(1)\n\nif __name__ == '__main__':\n    main()\n",
            encoding="utf-8",
        )
        result = runner.run(tmpdir)
        assert result.passed is False
        assert "bad_test.py" in result.failed_tests
        assert "good_test.py" not in result.failed_tests

    # --- Agent integration: run_tests and run_test_file log lifecycle events ---
    with tempfile.TemporaryDirectory() as tmpdir:
        from agent.agent import HephaestusAgent

        log_path = Path(tmpdir) / "test.log"
        agent = HephaestusAgent(log_path=str(log_path))

        passing = Path(tmpdir) / "agent_pass_test.py"
        passing.write_text(
            "def main():\n    print('PASS')\n\nif __name__ == '__main__':\n    main()\n",
            encoding="utf-8",
        )

        result = agent.run_test_file(str(passing))
        assert result.passed is True

        log_contents = log_path.read_text(encoding="utf-8")
        assert "TEST_RUN_START" in log_contents
        assert "TEST_RUN_COMPLETE" in log_contents

        # Failing file logs TEST_FAILURES
        failing = Path(tmpdir) / "agent_fail_test.py"
        failing.write_text(
            "import sys\nif __name__ == '__main__':\n    sys.exit(1)\n",
            encoding="utf-8",
        )
        result = agent.run_test_file(str(failing))
        assert result.passed is False
        assert "TEST_FAILURES" in log_path.read_text(encoding="utf-8")

    print("PASS")
    print("Test runner test passed")


if __name__ == "__main__":
    main()
