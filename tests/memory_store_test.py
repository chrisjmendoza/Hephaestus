"""Tests for MemoryStore per-repo persistence."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


def main() -> None:
    """Test MemoryStore read/write, slugging, and context summary."""
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from agent.memory_store import MemoryStore

    # ------------------------------------------------------------------
    # 1. New store starts empty
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        store = MemoryStore.for_repo(".", memory_root=tmpdir)
        assert store.records == [], f"Expected empty records, got: {store.records}"
        assert store.context_summary() == "", "Expected empty context summary"
    print("PASS: new store is empty")

    # ------------------------------------------------------------------
    # 2. record() persists to disk immediately
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        store = MemoryStore.for_repo("my-repo", memory_root=tmpdir)
        rec = store.record("fix login bug", "success", files_changed=["auth.py"])
        assert rec.task == "fix login bug"
        assert rec.outcome == "success"
        # File must exist on disk
        slug = MemoryStore._slug("my-repo")
        store_file = Path(tmpdir) / "repos" / f"{slug}.json"
        assert store_file.exists(), "Store file not created on disk"
        payload = json.loads(store_file.read_text())
        assert len(payload["tasks"]) == 1
        assert payload["tasks"][0]["files_changed"] == ["auth.py"]
    print("PASS: record persists to disk")

    # ------------------------------------------------------------------
    # 3. Data survives reload
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        store = MemoryStore.for_repo("reload-test", memory_root=tmpdir)
        store.record("task one", "success")
        store.record("task two", "failed", error="oops")
        # Reload from disk
        store2 = MemoryStore.for_repo("reload-test", memory_root=tmpdir)
        assert len(store2.records) == 2
        assert store2.records[1].error == "oops"
    print("PASS: data survives reload")

    # ------------------------------------------------------------------
    # 4. recent() returns last n records
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        store = MemoryStore.for_repo("paging", memory_root=tmpdir)
        for i in range(8):
            store.record(f"task {i}", "success")
        recent = store.recent(3)
        assert len(recent) == 3
        assert recent[-1].task == "task 7"
    print("PASS: recent(n) returns last n records")

    # ------------------------------------------------------------------
    # 5. context_summary() produces expected text
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        store = MemoryStore.for_repo("summary-test", memory_root=tmpdir)
        store.record("add caching", "success", files_changed=["cache.py", "app.py"])
        store.record("fix auth", "failed", error="test failures")
        summary = store.context_summary(n=5)
        assert "Recent task history" in summary
        assert "add caching" in summary
        assert "cache.py" in summary
        assert "fix auth" in summary
        assert "test failures" in summary
    print("PASS: context_summary contains expected content")

    # ------------------------------------------------------------------
    # 6. Slug is stable and filesystem-safe
    # ------------------------------------------------------------------
    assert MemoryStore._slug("My Repo!") == "my_repo"
    assert MemoryStore._slug("owner/target-repo") == "owner_target-repo"
    assert MemoryStore._slug("") == "unknown"
    print("PASS: slug generation is stable and safe")

    # ------------------------------------------------------------------
    # 7. Agent wires MemoryStore and records outcome after run_task
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        from unittest.mock import MagicMock, patch
        from agent.agent import HephaestusAgent

        log_path = Path(tmpdir) / "test.log"
        agent = HephaestusAgent(log_path=str(log_path))
        # Inject a temp memory store so we don't write to the real memory/repos/
        agent.memory = MemoryStore(Path(tmpdir) / "repos" / "test.json")

        plan = ["Search for relevant files"]
        with patch.object(agent, "generate_task_plan", return_value=plan):
            with patch.object(agent, "semantic_search", return_value=["main.py"]):
                agent.run_task("find the entry point")

        assert len(agent.memory.records) == 1
        rec = agent.memory.records[0]
        assert "find the entry point" in rec.task
        assert rec.outcome in ("success", "partial", "failed")
    print("PASS: agent records task outcome in memory after run_task")

    # ------------------------------------------------------------------
    # 8. Memory context is passed into generate_task_plan
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        from unittest.mock import MagicMock, patch
        from agent.agent import HephaestusAgent

        log_path = Path(tmpdir) / "test.log"
        agent = HephaestusAgent(log_path=str(log_path))
        agent.memory = MemoryStore(Path(tmpdir) / "repos" / "test.json")
        agent.memory.record("prior task", "failed", error="tests broke")

        captured_task: list[str] = []

        def mock_generate_plan(task: str, repo_path: str = ".") -> list[str]:
            captured_task.append(task)
            return ["Search step"]

        with patch.object(agent.task_reasoner, "generate_plan", side_effect=mock_generate_plan):
            agent.generate_task_plan("new feature")

        assert captured_task, "generate_plan was not called"
        assert "prior task" in captured_task[0] or "Recent task history" in captured_task[0], \
            f"Memory context not in enriched task: {captured_task[0]!r}"
    print("PASS: memory context is included in task sent to LLM")

    print("\n=== memory_store tests PASSED ===")


if __name__ == "__main__":
    main()
