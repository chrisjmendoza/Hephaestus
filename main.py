"""Entry point for the Hephaestus development agent."""

from __future__ import annotations

import sys

from agent.agent import HephaestusAgent


def main() -> None:
    """Parse CLI input, run the agent task loop, and print results."""
    if len(sys.argv) < 2:
        print("Usage: python main.py \"<task>\"")
        return

    task = " ".join(sys.argv[1:]).strip()
    print("Starting Hephaestus...")
    agent = HephaestusAgent()
    result = agent.run_task(task)
    print(result)


if __name__ == "__main__":
    main()
