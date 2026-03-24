# Hephaestus

Hephaestus is a local AI software engineering assistant project focused on safe, incremental development workflows.

Current version includes foundational orchestration plus repository introspection and LLM-assisted task planning features.

## What is Hephaestus

Hephaestus is designed to accept software development tasks, create a plan, and execute steps through a controlled tool layer.

Current scope focuses on architecture, readability, and modularity rather than full AI integration.

## Current capabilities

- Task loop execution with lifecycle logging.
- Multi-language repository scanning and structural indexing.
- Repository index querying (Python files, tests, entrypoints, directory summary).
- Semantic repository search over Python/Kotlin/Java/JS/C#/C++ sources (with XML support for small files).
- Embedding cache with mtime tracking — unchanged files are skipped on rebuild, modified files are re-embedded, removed files are evicted.
- Task reasoning and structured plan generation using repository context.
- File patching with unified diff preview and dry-run safety mode.
- Test execution with structured pass/fail results and failure reporting.
- Git-aware workflow: dirty-state detection, working-tree diff, and auto-commit of agent-applied patches.
- Structured task reports: JSON + human-readable summary of plan, patches, test outcomes, and commits, persisted to memory.

## CLI commands

- `python main.py "<task>"`
- `python main.py scan <repo_path>`
- `python main.py query <python|tests|entrypoints|dirs>`
- `python main.py semantic "<query>" --repo <path>`
- `python main.py plan "<task>"`

## Project structure

- `main.py`: CLI entry point for task, scan, query, and semantic commands.
- `agent/agent.py`: Core orchestration class (`HephaestusAgent`).
- `agent/planner.py`: Task planning logic.
- `agent/tools.py`: Safe tool interface.
- `agent/repo_scanner.py`: Multi-language repository scan and index generation.
- `agent/repo_query.py`: Repository index query helpers.
- `agent/repo_semantic.py`: Semantic index build and semantic search.
- `agent/task_reasoner.py`: LLM-based task plan generation using semantic repository context.
- `agent/patch_executor.py`: File patching with unified diff generation and dry-run support.
- `agent/test_runner.py`: Test execution via pytest (with direct-run fallback) and structured result reporting.
- `agent/git_context.py`: Git status inspection, working-tree diff, and auto-commit for agent patches.
- `agent/task_report.py`: Structured task report generation, persistence, and human-readable rendering.
- `prompts/dev_agent.md`: System prompt/instructions.
- `memory/`: Runtime memory artifacts (`repo_index.json`, `repo_embeddings.json`, `task_plan.json`) and static memory files.
- `logs/`: Agent runtime logs.
- `tests/`: Smoke tests for lifecycle, scan, query, semantic search, and multi-language indexing.
- `requirements.txt`: Python dependencies.

## Logging lifecycle events

- Task loop: `TASK_RECEIVED`, `PLAN_CREATED`, `STEP_START`, `STEP_COMPLETE`, `TASK_COMPLETE`
- Repository scan: `REPO_SCAN_START`, `REPO_LANGUAGE_DETECTED`, `REPO_SCAN_COMPLETE`
- Repository query: `REPO_QUERY_START`, `REPO_QUERY_COMPLETE`
- Semantic search: `SEMANTIC_SEARCH_START`, `MULTILANG_INDEX_BUILD`, `SEMANTIC_SEARCH_COMPLETE`
- Task reasoning: `TASK_REASON_START`, `TASK_REASON_COMPLETE`
- Patch execution: `PATCH_START`, `PATCH_PREVIEW`, `PATCH_APPLIED`, `PATCH_SKIPPED`
- Test execution: `TEST_RUN_START`, `TEST_RUN_COMPLETE`, `TEST_FAILURES`
- Git workflow: `GIT_STATUS_START`, `GIT_STATUS_COMPLETE`, `GIT_DIFF_START`, `GIT_DIFF_COMPLETE`, `GIT_COMMIT_START`, `GIT_COMMIT_COMPLETE`
- Task reporting: `TASK_REPORT_START`, `TASK_REPORT_COMPLETE`

## Future goals

- Replace placeholder planning with LLM-backed planning.
- Add deeper repository-aware editing and patch planning.
- Introduce safety checks, dry-runs, and patch previews.
- Persist reusable repository knowledge in memory.
- Add test orchestration and richer execution reporting.
