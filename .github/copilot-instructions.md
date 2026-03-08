# Hephaestus AI Development Guidelines

This repository implements an experimental AI software engineering agent.

AI coding assistants working in this repository must prioritize:

- safety
- observability
- modular architecture
- minimal patches
- reproducibility

The system is designed to evolve toward autonomous software maintenance.

## 1. Project Purpose

Hephaestus is an experimental AI software engineering assistant designed to help develop and maintain other software projects.

Its responsibilities will eventually include:

- task planning
- repository analysis
- patch generation
- automated testing
- reporting

This repository contains the infrastructure that enables those capabilities.

## 2. Core Architecture

Main components:

- `agent/`: core agent orchestration
- `agent/planner.py`: task planning logic
- `agent/tools.py`: system tool interface
- `prompts/`: AI system prompts
- `memory/`: persistent agent memory
- `logs/`: execution logging
- `main.py`: command line entry point

The system follows an **agent loop architecture**:

`task → plan → execute → verify → report`

## 3. Development Rules for AI Agents

AI assistants must follow these rules:

- Keep changes minimal and focused.
- Do not refactor unrelated code.
- Do not remove logging or observability features.
- Avoid introducing new dependencies unless necessary.
- Prefer clarity over cleverness.
- Ensure existing functionality continues to work.

## 4. Safety Constraints

AI agents must never:

- modify files outside the repository
- delete directories
- commit large structural changes without explanation
- bypass logging mechanisms
- disable tests

## 5. Testing Requirements

Before any code change is considered complete:

- smoke tests must pass
- agent lifecycle must remain functional
- logs must still be generated

## 6. Logging Requirements

Logging is critical for understanding agent behavior.

Do not remove or weaken logging output.

Lifecycle events must remain visible:

- `TASK_RECEIVED`
- `PLAN_CREATED`
- `STEP_START`
- `STEP_COMPLETE`
- `TASK_COMPLETE`

## 7. Future Architecture (Reference)

Future versions of Hephaestus will add:

- LLM reasoning
- repository indexing
- patch generation
- CI integration
- autonomous issue resolution

AI assistants should preserve modularity to support these future features.

## 8. Commit Message Standards

Commit messages must be readable and informative without requiring code diff inspection.

Use this structure:

1. Title line: concise scope + version context when relevant.
2. One-sentence summary: what capability changed.
3. `Capabilities:` list: key behaviors added/changed.
4. `Validation:` short test status summary.

Guidelines:

- Prefer clear, plain language over terse shorthand.
- Include user-facing command changes when applicable.
- Mention new lifecycle logging events when added.
- Mention important helper methods/classes introduced.
- Keep subject focused on one change set.

Preferred style example:

`v0.4 — Semantic repository search`

`Adds semantic indexing and search using sentence-transformers.`

`Capabilities:`
- `Builds local embedding index for repository files`
- `Semantic search returns top relevant files`
- `CLI command: main.py semantic "<query>"`
- `Agent helper: semantic_search()`
- `Logging events for semantic search lifecycle`

`Validation:`
- `All tests passing`

## AI Operating Contract

AI assistants modifying this repository must:

1. Read existing files before editing them.
2. Avoid modifying multiple subsystems in one change.
3. Prefer incremental improvements over rewrites.
4. Maintain lifecycle logging events used by smoke tests.
5. Preserve compatibility with the agent execution loop.
