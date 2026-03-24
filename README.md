# Hephaestus

Hephaestus is a local AI software engineering assistant project focused on safe, incremental development workflows.

Current version includes foundational orchestration, repository introspection, LLM-assisted task planning, GitHub API integration, an end-to-end issue resolution pipeline, and private repository support via `GITHUB_TOKEN`.

## What is Hephaestus

Hephaestus is designed to accept software development tasks, create a plan, and execute steps through a controlled tool layer.

Current scope focuses on architecture, readability, and modularity rather than full AI integration.

## Configuration

Hephaestus reads secrets from a `.env` file at the project root (loaded automatically on startup).  Copy `.env.example` to `.env` and fill in your values:

```
cp .env.example .env
# then edit .env with your tokens
```

| Variable | Purpose |
|---|---|
| `GITHUB_TOKEN` | GitHub PAT with `repo` scope — enables issue/PR API access **and** cloning private repos |
| `OPENAI_API_KEY` | OpenAI key for LLM-backed planning (future feature) |

`.env` is gitignored and will never be committed.

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
- GitHub API client: fetch issues, list issues by label, post comments, create branches, and open pull requests via `GITHUB_TOKEN`.
- Issue resolver loop: end-to-end plan → patch → test → commit → PR pipeline triggered by a task description or GitHub issue; includes dry-run mode and tests-pass gate.
- Target repository manager: clone, pull, and branch-manage external repositories into a local `workspace/` directory; supports `ensure_workspace()` for one-call setup before running the resolver.  Private repositories are accessed automatically when `GITHUB_TOKEN` is set.

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
- `agent/github_client.py`: GitHub API wrapper for issues, comments, branches, and pull requests.
- `agent/issue_resolver.py`: End-to-end issue resolution orchestrator (plan → patch → test → commit → PR).
- `agent/repo_manager.py`: Target repository manager — clone, pull, and branch external repos into a local workspace.
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
- GitHub API: `GH_GET_ISSUE_START/COMPLETE`, `GH_LIST_ISSUES_START/COMPLETE`, `GH_COMMENT_START/COMPLETE/FAILED`, `GH_CREATE_BRANCH_START/COMPLETE/FAILED`, `GH_OPEN_PR_START/COMPLETE/FAILED`
- Issue resolution: `RESOLVE_ISSUE_START`, `RESOLVE_ISSUE_COMPLETE`, `RESOLVE_ISSUE_FAILED`
- Workspace management: `WORKSPACE_CLONE_START/COMPLETE`, `WORKSPACE_PULL_START/COMPLETE`, `WORKSPACE_CHECKOUT_START/COMPLETE/FAILED`, `WORKSPACE_ENSURE_START/COMPLETE`, `WORKSPACE_LIST_START/COMPLETE`

## Future goals

- Replace placeholder planning with LLM-backed planning.
- Add deeper repository-aware editing and patch planning.
- Introduce safety checks, dry-runs, and patch previews.
- Persist reusable repository knowledge in memory.
- Add test orchestration and richer execution reporting.
