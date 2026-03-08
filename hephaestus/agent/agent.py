"""Core orchestration logic for the Hephaestus development agent."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .planner import TaskPlanner
from .tools import run_command


class HephaestusAgent:
    """Orchestrates planning and step execution for development tasks."""

    def __init__(
        self,
        prompt_path: str = "prompts/dev_agent.md",
        log_path: str = "logs/hephaestus.log",
    ) -> None:
        """Initialize dependencies and load instruction prompt."""
        self.prompt_path = Path(prompt_path)
        self.log_path = Path(log_path)
        self.planner = TaskPlanner()
        self.instructions = self.prompt_path.read_text(encoding="utf-8")

    def run_task(self, task: str) -> str:
        """Create a plan and execute steps for the given task."""
        output_lines = ["Hephaestus initialized", f"Task received: {task}"]
        self.log(f"TASK_RECEIVED {task}")

        plan = self.planner.create_plan(task)
        self.log(f"PLAN_CREATED {plan}")
        output_lines.append(f"Plan generated: {plan}")
        output_lines.append("Executing steps")

        for step in plan:
            output_lines.append(self.execute_step(step))

        self.log("TASK_COMPLETE")
        output_lines.append("Task complete")
        return "\n".join(output_lines)

    def execute_step(self, step: str) -> str:
        """Execute one plan step using placeholder tool behavior."""
        self.log(f"STEP_START {step}")
        result = run_command("echo step executed")
        self.log(f"STEP_COMPLETE {step} | {result}")
        return f"{step}: {result}"

    def log(self, message: str) -> None:
        """Append a timestamped message to the agent log file."""
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.log_path.open("a", encoding="utf-8") as file:
            file.write(f"[{timestamp}] {message}\n")
