# Hephaestus Roadmap

Current version: **v2.15**

This file tracks where Hephaestus is headed and why each step matters.

---

## What Hephaestus does today

- Accepts a natural-language task
- Uses an LLM (Anthropic Claude) to generate a step-by-step plan based on the actual repo files
- Executes each step by intent: search, read, patch, test, or commit
- Logs every lifecycle event for observability
- Can interact with GitHub (issues, PRs, branches) and manage cloned workspaces

The execution loop is real end-to-end: `task → plan → execute → report`.

---

## Remaining steps

### Step 2 — Wire `dev_agent.md` into the LLM system prompt ✅ *done in v2.6*

**What it does:** Every time Hephaestus calls the LLM to plan or patch, it currently sends a
generic hardcoded system message ("You are an experienced software engineer…").
`prompts/dev_agent.md` contains the project's actual operating instructions:

> *"You are Hephaestus. Never modify large parts of the repository at once. Always analyze before
> editing. Prefer minimal patches. Ensure tests pass. Follow project architecture."*

Wiring this in means the LLM plans in character — aware it's Hephaestus, not a generic assistant.
Plans will trend toward smaller, safer, more architectural changes matching the project's principles.

**Why it matters:** Without this, the LLM ignores the project's own safety rules. With it, the
system prompt and the copilot instructions are consistent — the agent behaves the way the project
intends.

---

### Step 3 — `resolve <issue_number>` CLI command ✅ *done in v2.7*

**What it does:** Adds a new top-level command to `main.py`:

```
python main.py resolve 42
```

This will fetch GitHub issue #42, run the full `resolve_issue()` pipeline
(plan → patch → test → commit → PR), and print a summary. The infrastructure
(`IssueResolver`, `GitHubClient`) already exists — this just surfaces it from the CLI.

**Why it matters:** This is Hephaestus's core end-user capability. Without a CLI entry point,
the full pipeline is only accessible programmatically.

---

### Step 4 — Memory: per-repo task history ✅ *done in v2.8*

**What it does:** Adds `agent/memory_store.py` — a `MemoryStore` class that persists task
outcomes per repository under `memory/repos/{slug}.json`. At startup the agent loads the
store; after each run it records the outcome (success / partial / failed). The last 5
records are summarised and injected into the LLM context before planning, giving
Hephaestus awareness of what worked or failed previously.

**Why it matters:** Without memory, every task starts cold. With it, Hephaestus can avoid
repeating mistakes and build context across sessions — a prerequisite for autonomous maintenance.

---

### Step 5 — `--dry-run` CLI flag ✅ *done in v2.9*

**What it does:** Adds a `--dry-run` flag to `run_task` (and `resolve`) that previews plans and
diffs without writing files or committing. Patch, test, and commit steps print their intended
action with a `[dry-run]` prefix and stop. Read-only steps (search, read/inspect) still execute.
A `DRY_RUN_ENABLED` lifecycle event is logged when active.

**Why it matters:** Required for safe human review before Hephaestus operates autonomously on a
real repository. Lets you see exactly what the agent would do before it does it.

---

### Step 6 — README update ✅ *done in v2.10*

**What it does:** Rewrites `README.md` to accurately describe v2.x capabilities: Anthropic
backend, `dev_agent.md` system prompt, per-repo memory, live `execute_step` dispatcher,
`--dry-run` mode, `resolve` CLI command, environment setup, and the agent loop dispatch table.

**Why it matters:** The README previously described the early stub version. New contributors (or
a future autonomous agent working on this repo) would have been misled by it.

---

### Step 7 — Integration test against a real target repo ✅ *done in v2.11*

**What it does:** `tests/integration_test.py` — 5 tests that exercise the full stack
with real file I/O and real git operations using a fixture git repo created in a temp
directory. The LLM layer is mocked for determinism. Tests cover: `apply_patch` file
writes, `git_commit_patch` commit creation, `execute_step` implement+commit dispatch,
full `run_task` lifecycle (log events + memory), and dry-run no-write guarantee.

**Why it matters:** All prior tests mock the LLM and git layers. These tests confirm
the system works on real files and a real git repo — validating the full execution
chain outside a pure unit-test context.

---

## Priority summary

| # | Step | Value | Effort |
|---|------|-------|--------|
| 2 | Wire dev_agent.md into system prompt | High — agent behaves per defined rules | Tiny |
| 3 | `resolve` CLI command | High — core user-facing capability | Small |
| 4 | Memory read/write | Medium — enables continuity | Medium |
| 5 | `--dry-run` flag | Medium — safety for autonomous use | Small |
| 6 | README update | Low-Medium — docs accuracy | Small |
| 7 | Integration test | High — real-world validation | Large |
