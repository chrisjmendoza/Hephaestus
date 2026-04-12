# Hephaestus Roadmap

Current version: **v2.5**

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

### Step 4 — Memory: read/write `memory/memory.json`

**What it does:** Hephaestus currently has a `memory/memory.json` file but nothing reads or
writes it during task execution. This step adds:
- Load prior task history and decisions at startup
- Persist task outcomes (what was tried, what passed, what failed) after each run
- Optionally feed recent memory into the LLM context for better continuity

**Why it matters:** Without memory, every task starts cold. With it, Hephaestus can avoid
repeating mistakes and build context across sessions — a prerequisite for autonomous maintenance.

---

### Step 5 — `--dry-run` CLI flag

**What it does:** Adds a `--dry-run` flag to `run_task` (and `resolve`) that previews plans and
diffs without writing files or committing. All patch and commit steps print their intended action
and stop.

**Why it matters:** Required for safe human review before Hephaestus operates autonomously on a
real repository. Lets you see exactly what the agent would do before it does it.

---

### Step 6 — README update

**What it does:** Updates `README.md` to reflect v2.x capabilities: Anthropic backend, live
execute_step, CLI commands, environment setup, and the agent loop.

**Why it matters:** The README currently describes the early stub version. New contributors (or
a future autonomous agent working on this repo) will be misled by it.

---

### Step 7 — Integration test against a real target repo

**What it does:** A test that clones a small real (or fixture) repository, runs `run_task()` end-
to-end against it, and asserts that files were patched, tests ran, and a commit was produced.

**Why it matters:** All current tests mock the LLM and git layers. This test would exercise the
full stack — real LLM call, real file write, real git commit — confirming the system works
outside the Hephaestus repo itself.

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
