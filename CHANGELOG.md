# Changelog

All notable changes to Hephaestus are documented in this file.

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
