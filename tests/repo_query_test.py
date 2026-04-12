"""Repository query tests for Hephaestus."""

from __future__ import annotations

import json
import tempfile
import shutil
from pathlib import Path
import sys


def _setup() -> Path:
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    return project_root


def _make_index(tmp_dir: str) -> Path:
    """Write a controlled repo_index.json for unit tests."""
    from pathlib import Path as P
    index = {
        "python_files": ["agent/agent.py", "main.py"],
        "test_files": ["tests/smoke_test.py", "tests/repo_query_test.py"],
        "entrypoints": ["main.py"],
        "config_files": ["pyproject.toml", ".env"],
        "files": [
            "agent/agent.py",
            "agent/planner.py",
            "main.py",
            "tests/smoke_test.py",
            "README.md",
        ],
        "total_files": 5,
        "language_counts": {"Python": 3, "Markdown": 1},
    }
    index_path = P(tmp_dir) / "repo_index.json"
    index_path.write_text(json.dumps(index), encoding="utf-8")
    return index_path


def main() -> None:
    project_root = _setup()

    from agent.agent import HephaestusAgent
    from agent.repo_query import RepoQuery

    # ------------------------------------------------------------------
    # 1. Integration: get_python_files via real scan
    # ------------------------------------------------------------------
    index_path = project_root / "memory" / "repo_index.json"
    agent = HephaestusAgent(memory_root=str(project_root / "memory"))
    if not index_path.exists():
        agent.scan_repo(str(project_root))
    assert index_path.exists(), "Repository index file does not exist"
    python_files = agent.query_repo("python")
    assert len(python_files) > 0, "No Python files returned by repository query"
    print("PASS: get_python_files (integration)")

    # ------------------------------------------------------------------
    # 2. Unit: get_test_files
    # ------------------------------------------------------------------
    tmp = tempfile.mkdtemp()
    try:
        idx = _make_index(tmp)
        rq = RepoQuery(index_path=idx)
        tests = rq.get_test_files()
        assert "tests/smoke_test.py" in tests, f"Expected test file missing: {tests}"
        assert len(tests) == 2, f"Expected 2 test files, got {len(tests)}"
        print("PASS: get_test_files")
    finally:
        shutil.rmtree(tmp)

    # ------------------------------------------------------------------
    # 3. Unit: get_entrypoints
    # ------------------------------------------------------------------
    tmp = tempfile.mkdtemp()
    try:
        idx = _make_index(tmp)
        rq = RepoQuery(index_path=idx)
        entrypoints = rq.get_entrypoints()
        assert "main.py" in entrypoints, f"Expected entrypoint missing: {entrypoints}"
        print("PASS: get_entrypoints")
    finally:
        shutil.rmtree(tmp)

    # ------------------------------------------------------------------
    # 4. Unit: get_config_files
    # ------------------------------------------------------------------
    tmp = tempfile.mkdtemp()
    try:
        idx = _make_index(tmp)
        rq = RepoQuery(index_path=idx)
        configs = rq.get_config_files()
        assert "pyproject.toml" in configs, f"Expected config file missing: {configs}"
        print("PASS: get_config_files")
    finally:
        shutil.rmtree(tmp)

    # ------------------------------------------------------------------
    # 5. Unit: get_directory_summary
    # ------------------------------------------------------------------
    tmp = tempfile.mkdtemp()
    try:
        idx = _make_index(tmp)
        rq = RepoQuery(index_path=idx)
        summary = rq.get_directory_summary()
        assert isinstance(summary, dict), "Expected dict from get_directory_summary"
        assert summary.get("agent") == 2, f"Expected 2 files in agent/, got {summary.get('agent')}"
        assert summary.get("tests") == 1, f"Expected 1 file in tests/, got {summary.get('tests')}"
        # root-level files (main.py, README.md) → "."
        assert summary.get(".") == 2, f"Expected 2 root files, got {summary.get('.')}"
        print("PASS: get_directory_summary")
    finally:
        shutil.rmtree(tmp)

    # ------------------------------------------------------------------
    # 6. Unit: load_index raises FileNotFoundError for missing file
    # ------------------------------------------------------------------
    tmp = tempfile.mkdtemp()
    try:
        rq = RepoQuery(index_path=Path(tmp) / "nonexistent.json")
        raised = False
        try:
            rq.load_index()
        except FileNotFoundError:
            raised = True
        assert raised, "Expected FileNotFoundError for missing index"
        print("PASS: load_index FileNotFoundError")
    finally:
        shutil.rmtree(tmp)

    # ------------------------------------------------------------------
    # 7. Unit: index cached — load_index not called twice
    # ------------------------------------------------------------------
    tmp = tempfile.mkdtemp()
    try:
        idx = _make_index(tmp)
        rq = RepoQuery(index_path=idx)
        first = rq.get_python_files()
        # Delete the file — second call should use cached _index
        idx.unlink()
        second = rq.get_python_files()
        assert first == second, "Cached index differed from first load"
        print("PASS: index caching (no redundant disk read)")
    finally:
        shutil.rmtree(tmp)

    print("\n=== repo_query tests PASSED ===")


if __name__ == "__main__":
    main()
