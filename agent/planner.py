"""Task planning module for Hephaestus."""

from __future__ import annotations


class TaskPlanner:
    """Creates a lightweight execution plan for a development task."""

    def create_plan(self, task: str) -> list[str]:
        """Return a placeholder plan for the provided task.

        Args:
            task: A natural-language development request.

        Returns:
            A list of ordered execution steps.
        """
        _ = task
        return [
            "Analyze repository",
            "Locate relevant files",
            "Plan modifications",
            "Implement changes",
            "Run tests",
        ]
