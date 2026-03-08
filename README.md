# Hephaestus

Hephaestus is a local AI software engineering assistant project focused on safe, incremental development workflows.

Current version includes foundational orchestration plus repository introspection features (scan, query, and semantic search).

## What is Hephaestus

Hephaestus is designed to accept software development tasks, create a plan, and execute steps through a controlled tool layer.

Current scope focuses on architecture, readability, and modularity rather than full AI integration.

## Current capabilities

- Task loop execution with lifecycle logging.
- Repository scanning and structural indexing.
- Repository index querying (Python files, tests, entrypoints, directory summary).
- Semantic repository search over Python files using local embeddings.

## CLI commands

- `python main.py "<task>"`
- `python main.py scan <repo_path>`
- `python main.py query <python|tests|entrypoints|dirs>`
- `python main.py semantic "<query>"`

## Project structure

- `main.py`: CLI entry point for task, scan, query, and semantic commands.
- `agent/agent.py`: Core orchestration class (`HephaestusAgent`).
- `agent/planner.py`: Task planning logic.
- `agent/tools.py`: Safe tool interface.
- `agent/repo_scanner.py`: Repository scan and index generation.
- `agent/repo_query.py`: Repository index query helpers.
- `agent/repo_semantic.py`: Semantic index build and semantic search.
- `prompts/dev_agent.md`: System prompt/instructions.
- `memory/`: Runtime memory artifacts (`repo_index.json`, `repo_embeddings.json`) and static memory files.
- `logs/`: Agent runtime logs.
- `tests/`: Smoke tests for lifecycle, scan, query, and semantic search.
- `requirements.txt`: Python dependencies.

## Logging lifecycle events

- Task loop: `TASK_RECEIVED`, `PLAN_CREATED`, `STEP_START`, `STEP_COMPLETE`, `TASK_COMPLETE`
- Repository scan: `REPO_SCAN_START`, `REPO_SCAN_COMPLETE`
- Repository query: `REPO_QUERY_START`, `REPO_QUERY_COMPLETE`
- Semantic search: `SEMANTIC_SEARCH_START`, `SEMANTIC_SEARCH_COMPLETE`

## Future goals

- Replace placeholder planning with LLM-backed planning.
- Add deeper repository-aware editing and patch planning.
- Introduce safety checks, dry-runs, and patch previews.
- Persist reusable repository knowledge in memory.
- Add test orchestration and richer execution reporting.
