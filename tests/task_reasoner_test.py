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


if __name__ == "__main__":
    main()
