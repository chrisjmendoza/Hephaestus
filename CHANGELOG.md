# Changelog

All notable changes to Hephaestus are documented in this file.

## v2.16 — Live pipeline fixes and observability (2026-04-12)

### Added
- `--repo <path>` flag on the `hep "<task>"` CLI command so tasks can target
  external repositories without needing `hep resolve`.
- Progress output in `run_task()`: prints `[step N/M] <step>` before each step
  so long tasks show visible progress.
- `generate_report()` is now called at the end of every `run_task()` execution,
  persisting a structured `TaskReport` alongside the memory record.
- `tests/run_task_test.py` — 5 new tests covering `repo_path` propagation, report
  generation, progress printing, and default behaviour.
- `tests/execute_step_test.py` — 4 new tests covering the semantic-search fallback
  path (P1.1), no-hits skip, LLM retry on unchanged content (P2.3), and the
  PATCH_FAILED lifecycle event.
- `tests/resolve_cli_test.py` — end-to-end integration test verifying the
  plan→patch→commit chain fires with mocked LLM (P3.3).

### Fixed
- **`execute_step` implement dispatch** — when no file-path token is present in a
  plan step, `semantic_search(step, top_k=1)` is used to identify the target file
  instead of falling through to `[skip]` (P1.1).
- **`run_task` `repo_path` propagation** — `run_task()` now accepts `repo_path`
  and threads it through to every `execute_step()` and `generate_task_plan()` call
  so steps operate against the correct repository (P1.2).
- **`resolve_issue` LLM loop** — `HephaestusAgent.resolve_issue()` now generates
  patches automatically when `patches=[]` by iterating plan steps through
  `semantic_search` + `generate_patch`, so `hep resolve N` self-generates patch
  content instead of creating an empty commit (P1.3).
- **Structured diff output** — `execute_step` implement result now includes the
  first 500 characters of the actual unified diff instead of a character count
  (P2.1).
- **Per-step error recovery** — when `generate_patch` returns the original content
  unchanged (LLM unavailable), `execute_step` logs a `PATCH_FAILED` event and
  retries once with a simplified instruction. A second unchanged result records
  `[skip] PATCH_FAILED` (P2.3).
- **`MemoryStore.for_repo` path** — `for_repo()`'s `memory_root` parameter now
  defaults to `memory_dir()` (config-resolved user data directory) so that
  bare `MemoryStore.for_repo(".")` calls persist memory in the correct location
  after `pip install` (P4.2).

## v2.15 — pytest testing infrastructure (2026-04-12)

### Added
- `conftest.py` — pytest plugin that collects `main()`-based test modules
  alongside standard `test_*` functions so the entire test suite runs with a
  single `pytest tests/` invocation.
- `pytest.ini` — minimal configuration: `testpaths = tests`, default addopts
  `-v --tb=short`.
- All existing `*_test.py` files discovered and executed correctly by pytest.

## v2.14 — Config module and `hep init` command (2026-04-12)

### Added
- `agent/config.py` — platform-aware user data directory resolution (`data_dir`,
  `logs_dir`, `memory_dir`, `prompts_dir`, `default_prompt_path`, `init_data_dir`).
- `hep init` CLI command scaffolds the user data directory on first run.
- `pyproject.toml` — `setuptools` package definition with `hep` entry point.

### Changed
- `HephaestusAgent.__init__()` defaults all path parameters to the config-resolved
  user data directory.

## v2.13 — Test coverage expansion (2026-04-12)

### Added
- `tests/cli_test.py` — 11 tests covering all previously-untested CLI dispatch
  branches: `scan`, `query` (all four sub-types), `semantic`, and `plan`, plus
  missing-argument usage-message assertions.
- `tests/repo_query_test.py` — expanded from 1 to 7 tests: `get_test_files`,
  `get_entrypoints`, `get_config_files`, `get_directory_summary`, `load_index`
  `FileNotFoundError` path, and index caching (no redundant disk read).
- `tests/task_reasoner_test.py` — 10 new assertions covering `_parse_plan_text`
  (numbered, bullet, blank lines, empty input), `_fallback_plan` (with and
  without relevant files), and `generate_patch` (no API key, exception fallback,
  markdown fence stripping, empty LLM response).

### Removed
- Dead `TaskPlanner` instantiation from `HephaestusAgent.__init__()` — `self.planner`
  was constructed but never called; the import has also been removed.  `agent/planner.py`
  is retained.

## v2.12 — `pyproject.toml` + user data directory (2026-04-12)

### Added
- `agent/config.py` — platform-aware user data directory resolution:
  - Windows: `%APPDATA%\Hephaestus`
  - macOS: `~/Library/Application Support/Hephaestus`
  - Linux: `$XDG_DATA_HOME/Hephaestus` (fallback `~/.local/share/Hephaestus`)
  - `data_dir()`, `logs_dir()`, `memory_dir()`, `prompts_dir()` helpers.
  - `default_prompt_path()` returns the user-dir `dev_agent.md`, copying the
    bundled source on first access.
  - `init_data_dir()` scaffolds all sub-directories and the prompt file; safe to
    call multiple times.
- `pyproject.toml` — `setuptools`-based package definition:
  - Package name `hephaestus-agent`, version `2.12.0`.
  - `[project.scripts]` entry point: `hep = main:main` (installs a `hep` command).
  - `[project.optional-dependencies]` dev extras: `pytest`, `pytest-cov`.
  - `[tool.setuptools.package-data]` includes `prompts/*.md`.
- `hep init` CLI command — scaffolds the user data directory and prints all
  sub-directory paths; safe to run on a fresh install before the first task.
- `tests/config_test.py` — 12 tests covering platform path resolution (Windows /
  Linux / macOS), sub-directory creation, `init_data_dir` idempotency, bundled
  prompt copy, `HephaestusAgent` path wiring, and `hep init` CLI output.

### Changed
- `HephaestusAgent.__init__()` now defaults all three path parameters
  (`prompt_path`, `log_path`, `memory_root`) to the config-resolved user data
  directory instead of hardcoded relative paths. Explicit paths can still be
  passed (existing tests are unaffected).

## v2.11 — Integration test suite (2026-04-12)

### Added
- `tests/integration_test.py` — 5 integration tests that exercise the full stack
  with real file I/O and real git operations (LLM layer mocked for determinism):
  - `test_apply_patch_modifies_real_file` — `apply_patch()` writes content to a
    real temp file and produces a valid unified diff.
  - `test_git_commit_creates_real_commit` — `git_commit_patch()` stages and commits
    a file in a real `git.Repo`, HEAD SHA advances.
  - `test_execute_step_patch_then_commit_on_fixture_repo` — `execute_step()` with
    an `implement` step then a `commit` step runs end-to-end on a fixture git repo:
    file is patched on disk, commit is created with the new content.
  - `test_run_task_full_lifecycle` — `run_task()` with analyze-only steps against
    the Hephaestus repo: all lifecycle events appear in log, memory is recorded.
  - `test_integration_dry_run_no_file_changes` — `execute_step()` with `dry_run=True`
    emits `[dry-run]` marker and leaves the fixture file unmodified.
- Fixture helpers: `_make_fixture_repo()` creates a minimal git repo (calculator.py
  + test_calculator.py + initial commit); `_cleanup()` handles Windows file-lock
  cleanup with `shutil.rmtree(ignore_errors=True)`.

## v2.10 — README rewrite (2026-04-11)

### Changed
- Rewrote `README.md` to reflect current v2.9 capabilities:
  - Accurate project description mentioning LLM reasoning, memory, and dry-run.
  - Updated capabilities list: per-repo memory, `dev_agent.md` system prompt wiring,
    dry-run preview, `execute_step` dispatcher.
  - CLI commands block now includes `resolve` and `--dry-run` options.
  - New **Environment setup** section with `.env` variable instructions.
  - Project structure updated with `memory_store.py` and corrected descriptions.
  - Logging events updated with `DRY_RUN_ENABLED` and `MEMORY_RECORDED`.
  - New **Agent loop** section with dispatch table showing intent-keyword routing.
  - Removed stale "Future goals" section (shipped features removed).

## v2.9 — --dry-run flag (2026-04-11)

### Added
- `--dry-run` flag on the default `run_task` CLI path:
  `python main.py "<task>" --dry-run` previews the full plan and shows what each step
  *would* do without writing any files or committing to git.
- `run_task(task, dry_run=False)` and `execute_step(step, repo_path, dry_run=False)`
  — destructive branches (implement/patch, test, commit) emit `[dry-run]` messages
  instead of performing real operations. Read-only branches (search, read) still execute.
- `DRY_RUN_ENABLED` lifecycle log event emitted when dry-run is active.
- `tests/dry_run_test.py` with 10 tests covering: per-branch dry-run skipping, search/read
  pass-through, `run_task` output markers, `DRY_RUN_ENABLED` log event, and CLI flag
  parsing.

## v2.8 — Per-repo task memory (2026-04-11)

### Added
- `agent/memory_store.py` — `MemoryStore` class that persists task history per repository
  under `memory/repos/{slug}.json`.
  - `TaskRecord` dataclass stores task description, outcome, date, files changed, and error.
  - `for_repo(repo_path, memory_root)` classmethod resolves the repo directory name and
    returns a store instance bound to that repo's file.
  - `record()` appends a new task record and persists to disk immediately.
  - `recent(n)` returns the last *n* task records.
  - `context_summary(n)` formats recent records as a plain-text summary suitable for
    prepending to an LLM prompt.
  - `_slug()` converts arbitrary repo names to filesystem-safe identifiers (lowercase,
    alphanumeric + `_` + `-`, defaults to `unknown` for empty names).
- `HephaestusAgent` now initialises a `MemoryStore` at startup and:
  - Injects `context_summary(n=5)` into the task string before each LLM planning call,
    giving the model awareness of recent outcomes.
  - Calls `memory.record()` after every `run_task()` execution, capturing success/partial/
    failed outcomes and any error text.
- `tests/memory_store_test.py` with 8 tests covering: empty store, persistence, reload,
  `recent(n)` slicing, context summary content, slug rules, agent wiring, and LLM context
  injection.

## v2.7 — resolve CLI command (2026-04-11)

### Added
- `python main.py resolve <issue_number>` CLI command.
  - Fetches the GitHub issue title/body (when `--github-repo owner/repo` is provided) and
    uses it as the task description.
  - Generates a plan via `generate_task_plan()`, prints it, then runs the full
    `resolve_issue()` pipeline (plan -> patch -> test -> commit -> PR).
  - Supports `--repo <path>` (default `.`), `--github-repo owner/repo`, and `--dry-run`.
  - Prints the PR URL on success; prints the error message on failure.
  - Falls back to a generic task description when no GitHub token or repo is provided.
- `tests/resolve_cli_test.py` with 5 tests covering: missing/invalid args, local dry-run
  dispatch, GitHub issue fetch + PR URL display, and failure message.

## v2.6 — Wire dev_agent.md into LLM system prompt (2026-04-11)

### Changed
- `TaskReasoner.__init__()` accepts a new `instructions: str = ""` parameter.
  When set, the instructions are used as the base system message for every LLM call
  (both `generate_plan()` and `generate_patch()`), with method-specific directives
  appended. Falls back to the previous generic system message when empty.
- `HephaestusAgent.__init__()` now passes `self.instructions` (loaded from
  `prompts/dev_agent.md`) to `TaskReasoner` at construction time.  All LLM plan
  and patch calls are now guided by the project's own operating rules:
  prefer minimal patches, analyze before editing, follow project architecture.

### Added
- `tests/task_reasoner_test.py` expanded with two new assertions:
  - Verifies `agent.task_reasoner.instructions` matches the loaded `dev_agent.md` content.
  - Verifies the custom instructions string appears in the system message sent to the LLM
    (mocked Anthropic client).

## v2.5 — Live execute_step: real patching and committing (2026-04-11)

### Changed
- `implement / apply / modify / edit / write` branch now performs real file patches:
  - Extracts a file-path token from the step text
  - Reads current file content
  - Calls `TaskReasoner.generate_patch()` to generate modified content via LLM
  - Applies the patch via `apply_patch()` and returns a diff-char count
  - Returns `[skip]` when no target file is identified or the file doesn't exist
- `commit` branch now performs real commits:
  - Calls `git_status()` to determine staged and unstaged files
  - Derives the commit message from the step text
  - Calls `git_commit_patch()` to stage and commit
  - Returns `[skip]` gracefully when no git repository is present or working tree is clean
- Keyword matching for `implement` branch switched to regex word-boundary (`\bimplement\b`) to
  prevent false matches on words like "implemented" inside commit-step text

### Added
- `TaskReasoner.generate_patch(instruction, file_path, current_content)` — LLM-powered method
  that returns a complete modified file given an instruction and the current content.
  Falls back to `current_content` when no API key is available.
- `tests/execute_step_test.py` expanded from 9 to 11 tests covering the real-patch and
  real-commit paths (mocked LLM / git), as well as graceful skip on missing file/repo.

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
