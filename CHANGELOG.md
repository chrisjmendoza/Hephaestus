# Changelog

All notable changes to Hephaestus are documented in this file.

## v2.4 — execute_step keyword dispatcher (2026-04-11)

### Changed
- `execute_step()` replaced with a real keyword dispatcher. Steps are now routed by intent:
  - `analyze / review / search / find / locate` → `semantic_search()` returning top matching files
  - `read / inspect / examine / look` → `read_file()` on any `.py/.kt/.java/.ts/.js/.cs/.md` path token in the step text
  - `implement / apply / modify / edit / write` → dry-run patch message (execution layer coming next)
  - `test / validate / verify` → `run_tests()`
  - `commit` → dry-run commit message
  - anything else → fallback `echo step executed`

### Added
- Added `tests/execute_step_test.py` with 9 tests covering all dispatch branches, graceful fallbacks, and lifecycle logging.

## v2.3 — Anthropic integration, unified planning, live repo search (2026-04-11)

### Changed
- Switched LLM backend from OpenAI to Anthropic (`anthropic` package). Default planning model: `claude-haiku-4-5-20251001`.
- `run_task()` now delegates to `generate_task_plan()` / `TaskReasoner` instead of the static `TaskPlanner` stub. Falls back to deterministic plan when no API key is set.
- `search_repo()` in `agent/tools.py` replaced placeholder string return with live `RepoSemanticIndex.search()`. Now returns `list[str]` of matching file paths.
- Fixed Anthropic response parsing to filter for `TextBlock` before accessing `.text` (avoids type errors on `ThinkingBlock`, `ToolUseBlock`, etc.)
- Replaced `openai` with `anthropic` in `requirements.txt`.
- Runtime memory artifacts (`repo_index.json`, `repo_embeddings.json`, `task_plan.json`) added to `.gitignore`.

### Added
- Added `load_dotenv()` call in `main.py` so a `.env` file is loaded at startup. `ANTHROPIC_API_KEY` and `HEPHAESTUS_PLAN_MODEL` can be set via `.env` or Windows User environment variables.

## v2.2 — Target repository manager (2026-03-24)

### Added
- Added `agent/repo_manager.py` with `RepoManager` class.
- `RepoManager.clone()`: clones a remote repository into a managed `workspace/owner/name` directory; no-op if already cloned.
- `RepoManager.pull()`: fast-forwards an existing clone from its remote.
- `RepoManager.checkout_branch()`: switches to an existing local branch or creates a new one (`create=True`).
- `RepoManager.ensure_workspace()`: convenience method that clone-or-pulls a repo and optionally checks out a branch in one call.
- `RepoManager.list_workspaces()`: returns `WorkspaceInfo` for every managed local clone.
- `RepoManager.local_path()`: returns the expected local path for an `owner/name` repository.
- `WorkspaceInfo` dataclass: `repo_name`, `local_path`, `branch`, `commit_sha`, `freshly_cloned`.
- `BranchCheckoutResult` dataclass: `success`, `branch_name`, `created`, `error`.
- Added `HephaestusAgent` wrappers: `workspace_clone()`, `workspace_pull()`, `workspace_checkout()`, `workspace_ensure()`, `workspace_list()` with lifecycle logging.
- Added lifecycle logs: `WORKSPACE_CLONE_START/COMPLETE`, `WORKSPACE_PULL_START/COMPLETE`, `WORKSPACE_CHECKOUT_START/COMPLETE/FAILED`, `WORKSPACE_ENSURE_START/COMPLETE`, `WORKSPACE_LIST_START/COMPLETE`.
- Added `tests/repo_manager_test.py` with 10 tests covering clone, no-op clone, pull, pull error, branch create, branch checkout, missing-branch error, ensure_workspace, list, and path structure.

### Changed
- Updated `README.md` to document repo manager capability, new module, and new lifecycle events.

## v2.1 — Issue resolver loop (2026-03-24)

### Added
- Added `agent/issue_resolver.py` with `IssueResolver` class and `ResolveResult` dataclass.
- `IssueResolver.resolve()`: full plan → patch → test → commit → report → PR pipeline in a single call.
- `IssueResolver.resolve_issue()`: convenience wrapper that derives the task from a `IssueInfo` object.
- `dry_run=True` mode: patches are previewed but not written; pipeline stops before commit and PR.
- Tests-pass gate: commit and PR are skipped (and error set) when tests fail.
- PR body auto-generated with plan steps, patch list, test summary, and issue close reference.
- Added `HephaestusAgent.resolve_issue()` with lifecycle logging: `RESOLVE_ISSUE_START`, `RESOLVE_ISSUE_COMPLETE`, `RESOLVE_ISSUE_FAILED`.
- Added `_get_resolver()` lazy initializer to `HephaestusAgent`.
- Added `tests/issue_resolver_test.py` with 5 tests covering dry-run, commit-no-PR, test-failure gate, full PR pipeline, and `resolve_issue()` wrapper.

### Changed
- Updated `README.md` to document issue resolver capability, new module, and new lifecycle events.

## v2.0 — GitHub API client (2026-03-24)

### Added
- Added `agent/github_client.py` with `GitHubClient` class.
- `GitHubClient.get_issue()`: fetch issue title, body, labels, state, and URL by number.
- `GitHubClient.list_issues()`: list issues filtered by label and state.
- `GitHubClient.post_comment()`: post a Markdown comment on an issue or PR, returns `CommentResult`.
- `GitHubClient.create_branch()`: create a remote branch from the tip of a base branch, returns `BranchResult`.
- `GitHubClient.open_pull_request()`: open a PR from a head branch into a base branch, returns `PullRequestResult`.
- All operations return structured dataclasses (`IssueInfo`, `CommentResult`, `BranchResult`, `PullRequestResult`) with an `error` field — no exceptions surface to the caller.
- Auth via `GITHUB_TOKEN` environment variable; falls back to unauthenticated access.
- Added `HephaestusAgent.gh_get_issue()`, `gh_list_issues()`, `gh_post_comment()`, `gh_create_branch()`, `gh_open_pr()` wrappers with lifecycle logging.
- Added lifecycle logs: `GH_GET_ISSUE_START/COMPLETE`, `GH_LIST_ISSUES_START/COMPLETE`, `GH_COMMENT_START/COMPLETE/FAILED`, `GH_CREATE_BRANCH_START/COMPLETE/FAILED`, `GH_OPEN_PR_START/COMPLETE/FAILED`.
- Added `PyGithub` to `requirements.txt`.
- Added `tests/github_client_test.py` with 7 mock-based tests (no live API calls required).

### Changed
- Updated `README.md` to document GitHub client capability and new lifecycle events.

## v1.0 — Structured task reporting (2026-03-24)

### Added
- Added `agent/task_report.py` with `TaskReporter`, `TaskReport`, `PatchEntry`, `TestEntry`, and `CommitEntry`.
- `TaskReporter.start()`: creates a new in-progress report with task and plan.
- `TaskReporter.record_patch()`, `record_test()`, `record_commit()`: append structured entries.
- `TaskReporter.finish()`: marks report complete with outcome and timestamp.
- `TaskReporter.persist()`: writes report to `memory/task_report.json` as JSON.
- `TaskReporter.load()`: reads and returns the last persisted report.
- `TaskReport.to_dict()`: JSON-serializable representation.
- `TaskReport.to_text()`: human-readable summary including plan, patches, test results, and commits.
- Added `HephaestusAgent.generate_report()` accepting patch, test, and commit results.
- Added lifecycle logs: `TASK_REPORT_START`, `TASK_REPORT_COMPLETE`.
- Added `tests/task_report_test.py` covering build, record, persist, load, text rendering, and agent integration.

### Changed
- Updated `README.md` to document task report capability and new lifecycle events.

## v0.9 — Git-aware workflow (2026-03-24)

### Added
- Added `agent/git_context.py` with `GitContext` class.
- `GitContext.status()`: returns `GitStatus` with branch, dirty flag, staged/unstaged/untracked file lists, HEAD sha and message.
- `GitContext.diff_working_tree()`: unified diff of unstaged changes (optionally scoped to one file).
- `GitContext.diff_staged()`: unified diff of staged changes vs HEAD.
- `GitContext.commit_patch()`: stages given file paths and creates a commit, returns `GitCommitResult`.
- Added `HephaestusAgent.git_status()`, `git_diff()`, and `git_commit_patch()` wrappers with lifecycle logging.
- Added lifecycle logs: `GIT_STATUS_START`, `GIT_STATUS_COMPLETE`, `GIT_DIFF_START`, `GIT_DIFF_COMPLETE`, `GIT_COMMIT_START`, `GIT_COMMIT_COMPLETE`.
- Added `tests/git_context_test.py` covering status, dirty detection, diff, commit, error handling, and agent integration.

### Changed
- Updated `README.md` to document git workflow capability and new lifecycle events.

## v0.8 — Embedding cache with mtime tracking (2026-03-24)

### Added
- Added mtime-based cache layer to `RepoSemanticIndex.build_index()`.
- Each persisted embedding entry now includes a `mtime` field.
- Unchanged files (mtime matches cache) are skipped entirely — no re-encode.
- Modified or new files are re-embedded and their cache entries updated.
- Files removed from the repo index are evicted from the embeddings cache.
- Added `tests/repo_semantic_cache_test.py` verifying cache hit, re-embed on change, and eviction.

### Changed
- `repo_embeddings.json` schema extended: each entry now has `path`, `mtime`, `embedding`.

## v0.7 — Test runner integration (2026-03-24)

### Added
- Added `agent/test_runner.py` with `TestRunner` class and `TestRunResult` dataclass.
- `TestRunner.run()`: runs pytest against a path, falls back to direct execution if pytest is absent.
- `TestRunner.run_file()`: runs a single Hephaestus-style test file directly.
- `TestRunResult` captures `exit_code`, `stdout`, `stderr`, `passed`, `summary`, and `failed_tests`.
- Added `HephaestusAgent.run_tests()` and `HephaestusAgent.run_test_file()` wrappers.
- Added test execution lifecycle logs: `TEST_RUN_START`, `TEST_RUN_COMPLETE`, `TEST_FAILURES`.
- Added `tests/test_runner_test.py` covering pass, fail, mixed directory, and agent integration.

### Changed
- Updated `README.md` to document test runner capability and new lifecycle events.

## v0.6 — Patch executor with dry-run support (2026-03-24)

### Added
- Added `agent/patch_executor.py` with `PatchExecutor` class.
- `PatchExecutor.apply()`: replace full file content with unified diff preview.
- `PatchExecutor.apply_replacement()`: replace a specific substring (validates uniqueness).
- `PatchResult` dataclass: captures `file_path`, `diff`, `applied`, `dry_run` outcome.
- Added `HephaestusAgent.apply_patch()` and `HephaestusAgent.apply_replacement()` wrappers.
- Added patch lifecycle logs: `PATCH_START`, `PATCH_PREVIEW`, `PATCH_APPLIED`, `PATCH_SKIPPED`.
- Added `tests/patch_executor_test.py` covering dry-run, live writes, and error cases.

### Changed
- Updated `README.md` to document patch executor capabilities and new lifecycle events.

## v0.5.1 — Multi-language repository support (2026-03-08)

### Added
- Added multi-language scan categories: `kotlin_files`, `java_files`, `js_files`, `xml_files`, `gradle_files`.
- Added additional scan categories: `csharp_files`, `cpp_files`.
- Added language summary in index: `language_counts`.
- Added multi-language scan smoke test `tests/repo_multilang_test.py`.

### Changed
- Extended scanner language detection for `.kt`, `.java`, `.js`, `.ts`, `.xml`, `.gradle`, `.kts`, `.cs`, and C++ source/header extensions.
- Added Android entrypoint detection: `MainActivity.kt`, `Application.kt`, `AndroidManifest.xml`.
- Extended semantic index sources to include Python/Kotlin/Java/JS/C#/C++ and small XML files.
- Limited semantic embedding content to first 1000 characters per file.
- Added semantic CLI repo targeting: `python main.py semantic "<query>" --repo <path>`.
- Added logs: `REPO_LANGUAGE_DETECTED`, `MULTILANG_INDEX_BUILD`.

## v0.5 — Task reasoning with repository context (2026-03-08)

### Added
- Added `agent/task_reasoner.py` with `TaskReasoner.generate_plan(task, repo_path=".")`.
- Added plan persistence to `memory/task_plan.json`.
- Added task reasoning smoke test `tests/task_reasoner_test.py`.

### Changed
- Added `HephaestusAgent.generate_task_plan(task, repo_path=".")`.
- Added reasoning lifecycle logs: `TASK_REASON_START`, `TASK_REASON_COMPLETE`.
- Added CLI command: `python main.py plan "<task>"`.
- Extended planning flow to use semantic repository context and file snippets.

## v0.4.2 — Documentation sweep and changelog governance (2026-03-08)

### Added
- Added this `CHANGELOG.md` to provide version-by-version project history.
- Added changelog maintenance guidance in `.github/copilot-instructions.md`.

### Changed
- Updated `README.md` to reflect implemented capabilities through v0.4.
- Added current CLI command coverage (`task`, `scan`, `query`, `semantic`) in docs.
- Added lifecycle logging/event coverage for task, scan, query, and semantic flows in docs.

## v0.4.1 — Commit message standards for AI agents (2026-03-08)

### Added
- Added commit message standards to `.github/copilot-instructions.md`.
- Introduced required commit structure: Title, summary, `Capabilities`, `Validation`.
- Added preferred commit example for semantic repository search.

## v0.4 — Semantic repository search (2026-03-08)

### Added
- Added `sentence-transformers` dependency.
- Added `agent/repo_semantic.py` with `RepoSemanticIndex`.
- Added local embedding persistence in `memory/repo_embeddings.json`.
- Added semantic smoke test `tests/repo_semantic_test.py`.

### Changed
- Added `HephaestusAgent.semantic_search()`.
- Added semantic lifecycle logs: `SEMANTIC_SEARCH_START`, `SEMANTIC_SEARCH_COMPLETE`.
- Added CLI command: `python main.py semantic "<query>"`.

## v0.3 — Repository query system (2026-03-08)

### Added
- Added `agent/repo_query.py` with index query helpers.
- Added query smoke test `tests/repo_query_test.py`.

### Changed
- Added `HephaestusAgent.query_repo(query_type)`.
- Added query lifecycle logs: `REPO_QUERY_START`, `REPO_QUERY_COMPLETE`.
- Added CLI command: `python main.py query <python|tests|entrypoints|dirs>`.
- Extended scan index payload to include `files` list for directory summaries.

## v0.2 — Repository awareness and indexing (2026-03-08)

### Added
- Added `agent/repo_scanner.py` with `RepoScanner.scan_repository()`.
- Added repository scan test `tests/repo_scan_test.py`.
- Added index output at `memory/repo_index.json`.

### Changed
- Added `HephaestusAgent.scan_repo(repo_path)`.
- Added scan lifecycle logs: `REPO_SCAN_START`, `REPO_SCAN_COMPLETE`.
- Added CLI command: `python main.py scan <repo_path>`.
- Added detection for Python files, tests, entrypoints, config files, and directories.

## v0.1.2 — Assertion-based smoke validation (2026-03-08)

### Changed
- Updated `tests/smoke_test.py` to assert required lifecycle events from logs.
- Added CI-friendly pass/fail behavior using Python assertions.

### Validated lifecycle events
- `TASK_RECEIVED`
- `PLAN_CREATED`
- `STEP_START`
- `STEP_COMPLETE`
- `TASK_COMPLETE`

## v0.1.1 — Operational loop smoke test (2026-03-08)

### Added
- Added initial smoke test `tests/smoke_test.py`.

### Changed
- Standardized runtime logging path to `logs/hephaestus.log`.
- Implemented explicit task/plan/step/task-complete operational flow.
- Improved `main.py` console progress output.

## v0.1 — Initial project scaffold (2026-03-08)

### Added
- Initial project structure for agent, prompts, memory, logs, tests, and CLI.
- Core modules: `agent.py`, `planner.py`, `tools.py`, `main.py`.
- Prompt file and memory bootstrap.
- Initial README and requirements setup.

## Repository housekeeping milestones (2026-03-08)

### Changed
- Flattened nested project folder so repository root contains source files and README for GitHub homepage rendering.
- Added `.gitignore` for local/env/editor/runtime artifacts.
- Added `logs/.gitkeep` so the logs directory exists in fresh clones.
- Added `.github/copilot-instructions.md` and project AI operating contract.
