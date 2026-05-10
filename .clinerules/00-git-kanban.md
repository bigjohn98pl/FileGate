# Git Kanban Workflow Rules

For every Kanban task, the remote base branch is the source of truth.

Default base ref: `main`, unless the user explicitly provides another base ref.

## Branch naming convention

Use the following prefix pattern for task branches:

| Prefix | Use case |
|---|---|
| `task/<slug>` | Regular Kanban task (default) |
| `feat/<slug>` | Feature-focused task |
| `fix/<slug>` | Bug fix |
| `poc/<slug>` | Proof of concept / exploration |
| `chore/<slug>` | Tooling, config, docs (no production code change) |

Examples: `task/mvp-01-runner-core`, `feat/artifact-schema-validation`, `fix/electron-path-normalization`

## Branch protection on `main`

`main` is protected with the following rules:

- **No direct pushes** — all changes must go through a pull request.
- **Linear history required** — use squash or rebase merge only (no merge commits).
- **All PR conversations must be resolved** before merge.
- **1 required approval** — repository owner can bypass as admin.

## Pre-flight before implementation

Before reading or editing project files for a task:

1. Run:

   ```bash
   git fetch --prune origin
   ```

2. Resolve the latest base commit:

   ```bash
   git rev-parse origin/{{base_ref}}
   ```

3. Report `base ref` and `START_BASE_SHA` before implementation.

4. Do not start implementation from a stale local branch if `origin/{{base_ref}}` is newer.

5. If working in a task worktree or detached HEAD, ensure the task branch is based on
   `origin/{{base_ref}}`, not on a stale local `{{base_ref}}`.

6. If the task branch already exists, rebase it onto the latest `origin/{{base_ref}}`
   before making new changes, unless the user explicitly says not to rebase.

## Dependent tasks (stacked branches)

If a task depends on another unmerged task:

- use the dependency branch as base instead of `{{base_ref}}`,
- fetch the dependency branch before implementation,
- report dependency branch name and SHA before coding.

## Before push / PR

Before pushing or opening a PR:

1. Fetch again:

   ```bash
   git fetch --prune origin
   ```

2. Rebase the task branch onto latest `origin/{{base_ref}}`.

3. Run relevant validation commands before PR creation.

## Required final task report

Final task report must include:

- base ref,
- base SHA used at task start,
- latest base SHA before PR,
- task branch,
- commit hash,
- whether rebase was performed,
- whether conflicts were resolved,
- test/validation result.
