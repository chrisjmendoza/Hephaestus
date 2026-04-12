# Hephaestus

Hephaestus is a local AI software engineering assistant designed to accept development tasks, reason about a repository, generate a plan, and execute steps safely — with full lifecycle logging and dry-run preview.

Current version: **v2.15**

## What is Hephaestus

Hephaestus accepts natural-language software development tasks, creates a structured plan using LLM reasoning over the actual repository files, and executes each step through a controlled tool layer. It can resolve GitHub issues end-to-end: fetch issue → plan → patch → test → commit → open PR.

## Current capabilities

- **Task loop**: `task → plan → execute → report` with full lifecycle logging.
- **LLM-guided planning**: `TaskReasoner` uses Anthropic Claude with the project's own `dev_agent.md` as its system prompt — plans follow the project's safety and architecture rules.
- **Per-repo memory**: task outcomes are persisted to `memory/repos/{repo}.json` and injected into the LLM context on the next run, giving the agent continuity across sessions.
- **Dry-run preview**: `--dry-run` on any command shows the full plan and what each step *would* do without writing files or committing.
- **execute_step dispatcher**: each plan step is routed by intent keyword — search, read, patch, test, or commit — to the appropriate tool.
- Multi-language repository scanning and structural indexing.
- Repository index querying (Python files, tests, entrypoints, directory summary).
- Semantic repository search over Python/Kotlin/Java/JS/C#/C++ sources.
- Embedding cache with mtime tracking — unchanged files are skipped on rebuild.
- File patching with unified diff preview and dry-run safety mode.
- Test execution with structured pass/fail results and failure reporting.
- Git-aware workflow: dirty-state detection, working-tree diff, and auto-commit of agent-applied patches.
- Structured task reports: JSON + human-readable summary of plan, patches, test outcomes, and commits.
- GitHub API client: fetch issues, list issues, post comments, create branches, open pull requests via `GITHUB_TOKEN`.
- Issue resolver loop: end-to-end plan → patch → test → commit → PR pipeline triggered by a task description or GitHub issue.
- Target repository manager: clone, pull, and branch external repositories into a local `workspace/` directory.

## CLI commands

```
hep "<task>" [--dry-run]
hep init
hep scan <repo_path>
hep query <python|tests|entrypoints|dirs>
hep semantic "<query>" --repo <path>
hep plan "<task>"
hep resolve <issue_number> [--repo <path>] [--github-repo owner/repo] [--dry-run]
```

## Installation

```
pip install .          # installs the hep command
# or for development:
pip install -e .[dev]
```

After installing, run `hep init` once to scaffold the user data directory:

```
hep init
```

This creates `logs/`, `memory/`, and `prompts/` under the platform data dir
(`%APPDATA%\Hephaestus` on Windows, `~/.local/share/Hephaestus` on Linux,
`~/Library/Application Support/Hephaestus` on macOS).

## Environment setup

```
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

Required environment variables (create a `.env` file or set in your shell):

```
ANTHROPIC_API_KEY=<your key>    # required for planning and patching
GITHUB_TOKEN=<your token>       # required for resolve --github-repo
```

## Project structure

- `agent/config.py`: Platform-aware user data directory — resolves `logs/`, `memory/`, `prompts/` to `%APPDATA%\Hephaestus` (Windows) or equivalent.
- `main.py`: CLI entry point.
- `agent/agent.py`: Core orchestration class (`HephaestusAgent`).
- `agent/planner.py`: Task planning logic.
- `agent/tools.py`: Safe tool interface (read_file, run_command).
- `agent/task_reasoner.py`: LLM-based plan and patch generation; uses `dev_agent.md` as system prompt.
- `agent/memory_store.py`: Per-repo task history — persists outcomes, injects context summary into LLM prompts.
- `agent/repo_scanner.py`: Multi-language repository scan and index generation.
- `agent/repo_query.py`: Repository index query helpers.
- `agent/repo_semantic.py`: Semantic index build and search.
- `agent/patch_executor.py`: File patching with unified diff generation and dry-run support.
- `agent/test_runner.py`: Test execution via pytest with structured result reporting.
- `agent/git_context.py`: Git status inspection, diff, and auto-commit for agent patches.
- `agent/task_report.py`: Structured task report generation and persistence.
- `agent/github_client.py`: GitHub API wrapper.
- `agent/issue_resolver.py`: End-to-end issue resolution orchestrator.
- `agent/repo_manager.py`: Target repository manager (clone/pull/branch into `workspace/`).
- `prompts/dev_agent.md`: Agent operating instructions — used as LLM system prompt.
- `memory/`: Runtime artifacts (`repo_index.json`, `repo_embeddings.json`, `task_plan.json`, `repos/`).
- `logs/`: Agent runtime logs.
- `tests/`: Smoke and unit tests.
- `requirements.txt`: Python dependencies.

## Logging lifecycle events

- Task loop: `TASK_RECEIVED`, `PLAN_CREATED`, `STEP_START`, `STEP_COMPLETE`, `TASK_COMPLETE`, `DRY_RUN_ENABLED`
- Memory: `MEMORY_RECORDED`
- Repository scan: `REPO_SCAN_START`, `REPO_LANGUAGE_DETECTED`, `REPO_SCAN_COMPLETE`
- Repository query: `REPO_QUERY_START`, `REPO_QUERY_COMPLETE`
- Semantic search: `SEMANTIC_SEARCH_START`, `MULTILANG_INDEX_BUILD`, `SEMANTIC_SEARCH_COMPLETE`
- Task reasoning: `TASK_REASON_START`, `TASK_REASON_COMPLETE`
- Patch execution: `PATCH_START`, `PATCH_PREVIEW`, `PATCH_APPLIED`, `PATCH_SKIPPED`
- Test execution: `TEST_RUN_START`, `TEST_RUN_COMPLETE`, `TEST_FAILURES`
- Git workflow: `GIT_STATUS_START/COMPLETE`, `GIT_DIFF_START/COMPLETE`, `GIT_COMMIT_START/COMPLETE`
- Task reporting: `TASK_REPORT_START`, `TASK_REPORT_COMPLETE`
- GitHub API: `GH_GET_ISSUE_START/COMPLETE`, `GH_LIST_ISSUES_START/COMPLETE`, `GH_COMMENT_START/COMPLETE/FAILED`, `GH_CREATE_BRANCH_START/COMPLETE/FAILED`, `GH_OPEN_PR_START/COMPLETE/FAILED`
- Issue resolution: `RESOLVE_ISSUE_START`, `RESOLVE_ISSUE_COMPLETE`, `RESOLVE_ISSUE_FAILED`
- Workspace management: `WORKSPACE_CLONE_START/COMPLETE`, `WORKSPACE_PULL_START/COMPLETE`, `WORKSPACE_CHECKOUT_START/COMPLETE/FAILED`, `WORKSPACE_ENSURE_START/COMPLETE`

## Agent loop

```
task → generate_task_plan() → [execute_step() × N] → memory.record() → report
```

Each `execute_step` dispatches by intent keyword:

| Keyword(s) | Action |
|---|---|
| analyze / review / search / find / locate | `semantic_search()` — top matching files |
| read / inspect / examine / look | `read_file()` on first path token found |
| implement / apply / modify / edit / write | `generate_patch()` → `apply_patch()` |
| test / validate / verify | `run_tests()` |
| commit | `git_commit_patch()` on staged/unstaged files |
| _(anything else)_ | `run_command("echo step executed")` |

In dry-run mode, the patch / test / commit rows print `[dry-run] Would …` instead of acting.
