# Hephaestus

Hephaestus is a local AI software engineering assistant project focused on safe, incremental development workflows.

Version 0.1 provides a minimal, extensible skeleton that can later support deeper AI planning and repository automation.

## What is Hephaestus

Hephaestus is designed to accept software development tasks, create a plan, and execute steps through a controlled tool layer.

Current scope focuses on architecture, readability, and modularity rather than full AI integration.

## Project structure

- `main.py`: Entry point that accepts a task and runs the agent loop.
- `agent/agent.py`: Core orchestration class (`HephaestusAgent`).
- `agent/planner.py`: Task planner with placeholder plan generation.
- `agent/tools.py`: Safe tool interface with minimal placeholder implementations.
- `prompts/dev_agent.md`: System prompt/instructions for agent behavior.
- `memory/memory.json`: Repository memory store (initialized empty).
- `logs/`: Agent runtime logs.
- `requirements.txt`: Minimal dependencies.

## Future goals

- Replace placeholder planning with LLM-backed planning.
- Add repository-aware search and edit tools.
- Introduce safety checks, dry-runs, and patch previews.
- Persist reusable repository knowledge in memory.
- Add test orchestration and richer execution reporting.
