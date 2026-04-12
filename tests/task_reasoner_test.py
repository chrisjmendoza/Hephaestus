"""Smoke-style task reasoning test for Hephaestus v0.5."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import sys


def main() -> None:
    """Generate a task plan and verify plan persistence."""
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from agent.agent import HephaestusAgent
    from agent.task_reasoner import TaskReasoner

    task_plan_path = project_root / "memory" / "task_plan.json"
    if task_plan_path.exists():
        task_plan_path.unlink()

    agent = HephaestusAgent()
    plan = agent.generate_task_plan("analyze repository structure", repo_path=str(project_root))

    assert len(plan) > 0, "Generated plan is empty"
    assert task_plan_path.exists(), "task_plan.json was not created"

    payload = json.loads(task_plan_path.read_text(encoding="utf-8"))
    assert len(payload.get("plan", [])) > 0, "Persisted plan is empty"

    print("PASS: plan generation and persistence")

    # ------------------------------------------------------------------
    # Verify instructions are passed from agent to TaskReasoner
    # ------------------------------------------------------------------
    instructions = agent.instructions.strip()
    assert instructions, "Agent failed to load instructions from dev_agent.md"
    assert agent.task_reasoner.instructions == instructions, \
        "TaskReasoner did not receive agent instructions"
    print("PASS: instructions wired into TaskReasoner")

    # ------------------------------------------------------------------
    # Verify instructions appear in the LLM system message
    # ------------------------------------------------------------------
    custom_instructions = "You are TestAgent. Always prefer minimal changes."
    reasoner = TaskReasoner(instructions=custom_instructions)
    mock_response = MagicMock()
    mock_text = MagicMock()
    mock_text.type = "text"
    mock_text.text = "1. Analyze\n2. Implement\n3. Test"
    mock_response.content = [mock_text]

    with patch("anthropic.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = mock_response
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            # Trigger build_index / scan via mock to skip real I/O
            with patch.object(reasoner.repo_scanner, "scan_repository", return_value={}):
                with patch.object(reasoner.repo_semantic, "build_index"):
                    with patch.object(reasoner.repo_semantic, "search", return_value=[]):
                        reasoner.generate_plan("add a feature", repo_path=".")

        call_kwargs = mock_client.messages.create.call_args
        system_used = call_kwargs.kwargs.get("system", "")
        assert custom_instructions in system_used, \
            f"Custom instructions not found in system message: {system_used!r}"
    print("PASS: custom instructions appear in LLM system message")

    print("\n=== task_reasoner tests PASSED ===")

    # ==================================================================
    # Unit tests for pure helper methods
    # ==================================================================

    # ------------------------------------------------------------------
    # _parse_plan_text — numbered list
    # ------------------------------------------------------------------
    steps = TaskReasoner._parse_plan_text("1. Analyze\n2. Implement\n3. Test")
    assert steps == ["Analyze", "Implement", "Test"], f"Unexpected steps: {steps}"
    print("PASS: _parse_plan_text numbered list")

    # ------------------------------------------------------------------
    # _parse_plan_text — bullet list
    # ------------------------------------------------------------------
    steps = TaskReasoner._parse_plan_text("- Step A\n- Step B\n- Step C")
    assert steps == ["Step A", "Step B", "Step C"], f"Unexpected steps: {steps}"
    print("PASS: _parse_plan_text bullet list")

    # ------------------------------------------------------------------
    # _parse_plan_text — blank lines ignored
    # ------------------------------------------------------------------
    steps = TaskReasoner._parse_plan_text("\n1. Only step\n\n")
    assert steps == ["Only step"], f"Unexpected steps: {steps}"
    print("PASS: _parse_plan_text blank lines ignored")

    # ------------------------------------------------------------------
    # _parse_plan_text — empty input returns empty list
    # ------------------------------------------------------------------
    steps = TaskReasoner._parse_plan_text("")
    assert steps == [], f"Expected empty list, got: {steps}"
    print("PASS: _parse_plan_text empty string")

    # ------------------------------------------------------------------
    # _fallback_plan — includes task and relevant files
    # ------------------------------------------------------------------
    plan = TaskReasoner._fallback_plan("fix a bug", ["agent/agent.py", "main.py"])
    assert len(plan) == 5, f"Expected 5 fallback steps, got {len(plan)}"
    assert any("fix a bug" in s for s in plan), "Task not mentioned in fallback plan"
    assert any("agent/agent.py" in s for s in plan), "Relevant file not in fallback plan"
    print("PASS: _fallback_plan with relevant files")

    # ------------------------------------------------------------------
    # _fallback_plan — no relevant files
    # ------------------------------------------------------------------
    plan = TaskReasoner._fallback_plan("do something", [])
    assert len(plan) == 5
    assert any("repository structure" in s for s in plan), \
        "Expected 'repository structure' fallback when no relevant files"
    print("PASS: _fallback_plan without relevant files")

    # ==================================================================
    # generate_patch tests
    # ==================================================================

    # ------------------------------------------------------------------
    # No API key → returns current_content unchanged
    # ------------------------------------------------------------------
    reasoner = TaskReasoner()
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}):
        result = reasoner.generate_patch("add a comment", "foo.py", "x = 1")
    assert result == "x = 1", f"Expected original content, got: {result!r}"
    print("PASS: generate_patch returns current_content when no API key")

    # ------------------------------------------------------------------
    # Exception during LLM call → returns current_content
    # ------------------------------------------------------------------
    reasoner = TaskReasoner()
    with patch("anthropic.Anthropic") as mock_cls:
        mock_cls.side_effect = Exception("network error")
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch.object(reasoner.repo_scanner, "scan_repository", return_value={}):
                result = reasoner.generate_patch("modify", "foo.py", "original")
    assert result == "original", f"Expected fallback content, got: {result!r}"
    print("PASS: generate_patch falls back on exception")

    # ------------------------------------------------------------------
    # Markdown fence stripping
    # ------------------------------------------------------------------
    reasoner = TaskReasoner()
    mock_resp = MagicMock()
    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = "```python\nx = 2\ny = 3\n```"
    mock_resp.content = [mock_block]

    with patch("anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = mock_resp
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            result = reasoner.generate_patch("update", "foo.py", "x = 1")

    assert result == "x = 2\ny = 3", f"Fence stripping failed, got: {result!r}"
    print("PASS: generate_patch strips markdown fences")

    # ------------------------------------------------------------------
    # Empty LLM response → returns current_content
    # ------------------------------------------------------------------
    reasoner = TaskReasoner()
    mock_resp2 = MagicMock()
    mock_block2 = MagicMock()
    mock_block2.type = "text"
    mock_block2.text = "   "
    mock_resp2.content = [mock_block2]

    with patch("anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = mock_resp2
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            result = reasoner.generate_patch("update", "foo.py", "fallback_content")

    assert result == "fallback_content", f"Expected fallback, got: {result!r}"
    print("PASS: generate_patch returns current_content on empty LLM response")

    print("\n=== ALL task_reasoner tests PASSED ===")


if __name__ == "__main__":
    main()
