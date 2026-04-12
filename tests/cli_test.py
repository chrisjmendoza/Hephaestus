"""CLI dispatch tests for Hephaestus main.py."""

from __future__ import annotations

import io
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


def _setup() -> None:
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


def _run_main(argv: list[str]) -> str:
    """Run main() with the given argv and capture stdout."""
    import main as main_module
    buf = io.StringIO()
    with patch("sys.argv", ["hep"] + argv):
        with patch("sys.stdout", buf):
            main_module.main()
    return buf.getvalue()


def main() -> None:
    _setup()

    # ------------------------------------------------------------------
    # 1. No arguments → prints usage
    # ------------------------------------------------------------------
    output = _run_main([])
    assert "Usage" in output, f"Expected usage message, got: {output!r}"
    print("PASS: no args prints usage")

    # ------------------------------------------------------------------
    # 2. scan — prints summary fields
    # ------------------------------------------------------------------
    fake_index = {
        "total_files": 10,
        "python_files": ["a.py", "b.py"],
        "test_files": ["tests/t.py"],
        "language_counts": {"Python": 9, "Markdown": 1},
        "entrypoints": ["main.py"],
        "config_files": ["pyproject.toml"],
    }
    with patch("agent.agent.HephaestusAgent.scan_repo", return_value=fake_index):
        output = _run_main(["scan", "."])
    assert "Total files: 10" in output, f"scan output missing total_files: {output}"
    assert "Python files: 2" in output, f"scan output missing python count: {output}"
    print("PASS: scan prints repository summary")

    # ------------------------------------------------------------------
    # 3. scan — missing path argument → prints usage
    # ------------------------------------------------------------------
    with patch("agent.agent.HephaestusAgent.scan_repo", return_value={}):
        output = _run_main(["scan"])
    assert "Usage" in output, f"Expected usage for missing scan arg: {output!r}"
    print("PASS: scan without path prints usage")

    # ------------------------------------------------------------------
    # 4. query python — prints file count
    # ------------------------------------------------------------------
    with patch("agent.agent.HephaestusAgent.query_repo", return_value=["a.py", "b.py"]):
        output = _run_main(["query", "python"])
    assert "Python files detected: 2" in output, f"query python output wrong: {output}"
    print("PASS: query python prints file count")

    # ------------------------------------------------------------------
    # 5. query tests
    # ------------------------------------------------------------------
    with patch("agent.agent.HephaestusAgent.query_repo", return_value=["tests/t.py"]):
        output = _run_main(["query", "tests"])
    assert "tests detected: 1" in output, f"query tests output wrong: {output}"
    print("PASS: query tests prints count")

    # ------------------------------------------------------------------
    # 6. query entrypoints
    # ------------------------------------------------------------------
    with patch("agent.agent.HephaestusAgent.query_repo", return_value=["main.py"]):
        output = _run_main(["query", "entrypoints"])
    assert "main.py" in output, f"query entrypoints output wrong: {output}"
    print("PASS: query entrypoints prints list")

    # ------------------------------------------------------------------
    # 7. query dirs
    # ------------------------------------------------------------------
    with patch("agent.agent.HephaestusAgent.query_repo", return_value={"agent": 5, "tests": 3}):
        output = _run_main(["query", "dirs"])
    assert "agent" in output and "5" in output, f"query dirs output wrong: {output}"
    print("PASS: query dirs prints directory summary")

    # ------------------------------------------------------------------
    # 8. semantic — prints top matches
    # ------------------------------------------------------------------
    with patch("agent.agent.HephaestusAgent.semantic_search", return_value=["agent/agent.py"]):
        output = _run_main(["semantic", "find the planner"])
    assert "agent/agent.py" in output, f"semantic output wrong: {output}"
    print("PASS: semantic prints top matches")

    # ------------------------------------------------------------------
    # 9. semantic — missing query → prints usage
    # ------------------------------------------------------------------
    with patch("agent.agent.HephaestusAgent.semantic_search", return_value=[]):
        output = _run_main(["semantic"])
    assert "Usage" in output, f"Expected usage for empty semantic: {output!r}"
    print("PASS: semantic without query prints usage")

    # ------------------------------------------------------------------
    # 10. plan — prints numbered steps
    # ------------------------------------------------------------------
    fake_plan = ["Analyze repo", "Write code", "Run tests"]
    with patch("agent.agent.HephaestusAgent.generate_task_plan", return_value=fake_plan):
        output = _run_main(["plan", "fix the bug"])
    assert "1. Analyze repo" in output, f"plan output wrong: {output}"
    assert "3. Run tests" in output, f"plan output missing last step: {output}"
    print("PASS: plan prints numbered steps")

    # ------------------------------------------------------------------
    # 11. plan — missing task arg → prints usage
    # ------------------------------------------------------------------
    with patch("agent.agent.HephaestusAgent.generate_task_plan", return_value=[]):
        output = _run_main(["plan"])
    assert "Usage" in output, f"Expected usage for missing plan arg: {output!r}"
    print("PASS: plan without task prints usage")

    print("\n=== cli tests PASSED ===")


if __name__ == "__main__":
    main()
