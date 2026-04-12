# Hephaestus TODO

Tracks next planned work in priority order. Each item links to the code area affected.

---

## Priority 1 — Blockers for live (non-dry-run) operation

These three issues mean live patching is effectively broken today.
Fix them in order: each one makes the next one more useful.

### 1.1 `execute_step` implement dispatch — use semantic search to find target file
**File:** `agent/agent.py` → `execute_step()` implement branch

The current logic scans for a file-path *token* in the step text (e.g. `"agent/agent.py"`).
LLM plan steps rarely include a bare path — they say *"Modify the task reasoner to handle edge
cases"*. The result is near-universal fallthrough to `[skip] No target file identified`.

**Fix:** call `semantic_search(step, top_k=1)` to get the most relevant file for the step,
then use that as the patch target. Fall back gracefully if no result.

---

### 1.2 `run_task` does not thread `repo_path` through to `execute_step`
**File:** `agent/agent.py` → `run_task()`

`execute_step(step, dry_run=dry_run)` is called without `repo_path`, so all steps operate against
`"."` regardless of which repo is being worked on.

**Fix:** add `repo_path: str = "."` to `run_task()` signature and pass it to every
`execute_step` call and to `generate_task_plan`.

---

### 1.3 `resolve_issue()` method expects pre-computed patches — LLM loop not wired in
**File:** `agent/agent.py` → `resolve_issue()` / `agent/issue_resolver.py`

`resolve_issue()` takes `patches: list[tuple[str, str]]` from the caller. The LLM
plan-then-patch loop in `run_task`/`execute_step` is never connected to it. Calling
`hep resolve N` fetches the issue and creates a branch but cannot self-generate patch content.

**Fix:** drive `resolve_issue` through `run_task` (or an equivalent loop that iterates plan
steps, calls `generate_patch` per step, collects results, then feeds them into the resolver).

---

## Priority 2 — Live-testing quality improvements

Once P1 is done, these raise quality from "sometimes works" to "reliably useful".

### 2.1 Structured diff output in `execute_step` implement result
**File:** `agent/agent.py` → `execute_step()` implement branch

Currently returns `"Patched {found}: {len(patch_result.diff)} diff chars"` — not actionable.
Should return the actual unified diff (or a short excerpt) in the step output so the task
report is human-readable. Also feed the `PatchResult` into `generate_report`.

---

### 2.2 `run_task` should call `generate_report` and persist the result
**File:** `agent/agent.py` → `run_task()`

`run_task` logs `TASK_COMPLETE` and records memory outcome, but never calls `generate_report`.
The `TaskReporter` and `PatchResult`/`TestRunResult` infra exist but are not connected here.

---

### 2.3 Per-step error recovery — retry once on LLM patch failure before skipping
**File:** `agent/agent.py` → `execute_step()` implement branch

If `generate_patch` returns the original content unchanged (LLM unavailable or empty response),
the step silently produces an empty diff and records `[skip]`. Should log a clear
`PATCH_FAILED` event and optionally retry once with a simplified instruction prompt.

---

### 2.4 `run_task` CLI should surface `repo_path` via `--repo` flag
**File:** `main.py`

`hep resolve` already has `--repo`. `hep "<task>"` has no way to point at a different repo.
Running tasks against a cloned external repo requires this — without it P1.2 is only useful
programmatically.

---

## Priority 3 — Test coverage for new/changed behaviour

Address after P1 fixes so tests reflect the corrected implementation.

### 3.1 `execute_step` implement tests — cover semantic-lookup path (post P1.1 fix)
**File:** `tests/execute_step_test.py`

Existing tests mock the semantic index. Add a test that verifies the implement branch
calls `semantic_search` when no file token is present, and patches the returned file.

---

### 3.2 `run_task` `repo_path` propagation test (post P1.2 fix)
**File:** `tests/execute_step_test.py` or new `tests/run_task_test.py`

Assert that `execute_step` is called with the `repo_path` supplied to `run_task`.

---

### 3.3 `resolve` CLI end-to-end test with mocked LLM (post P1.3 fix)
**File:** `tests/resolve_cli_test.py`

Existing tests only exercise the CLI argument parsing layer. Add one integration-level
test that confirms the full plan-→-patch-→-commit chain fires (LLM and git mocked).

---

## Priority 4 — Polish and observability

Low urgency; do after the live pipeline is stable.

### 4.1 Progress output in `run_task` — print step N of M during execution
**File:** `agent/agent.py` → `run_task()`

Currently prints `"Executing steps"` once then goes silent until done. Print
`"[step N/M] {step}"` before each step so the user can see progress on long tasks.

---

### 4.2 `memory/repos/` excluded from git but present in `memory_dir()`
**File:** `agent/memory_store.py` / `agent/config.py`

`MemoryStore.for_repo(".")` always writes to a relative `memory/repos/` path rather than
the config-resolved `memory_dir() / "repos"`. Align with the user data dir so memory
persists correctly after `pip install`.

---

### 4.3 CHANGELOG kept current
Update `CHANGELOG.md` when P1 items ship — currently missing v2.14 and v2.15 entries for
the config module and pytest infrastructure.
