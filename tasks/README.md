# Task Packs for Agents

## Purpose

This directory contains execution-ready tasks designed for coding agents.

## Structure

- `templates/agent-task-template.md` — canonical task format
- `poc/` — proof-of-concept task pack
- `mvp-agents/` — MVP implementation task pack

## Execution Principles

1. Execute tasks in listed order unless dependencies allow safe parallelism.
2. Follow scope and non-goals strictly.
3. Validate with listed checks before marking complete.
4. Produce explicit handoff notes for downstream tasks.

## Git Workflow Policy (Mandatory)

For every task:

1. Create and use a **separate branch**.
2. Complete implementation and validation on that branch.
3. Open a **Merge Request** after completion.
4. Wait for **maintainer approval** before merge.

No direct commits to the main branch are allowed for task execution.
