# Start Kanban Task

Use this workflow before implementing any Kanban task.

## Input

- base ref: `{{base_ref}}` (default `main`)
- task title: `{{task_title}}`
- task description: `{{task_description}}`
- optional dependency branch: `{{dependency_branch}}`

## Step 1: Sync remote refs

Run:

```bash
git fetch --prune origin
```

## Step 2: Determine latest base

If `dependency_branch` is provided, use it as base for this task:

```bash
git rev-parse origin/{{dependency_branch}}
```

Otherwise:

```bash
git rev-parse origin/{{base_ref}}
```

Store this as `START_BASE_SHA`.

## Step 3: Inspect worktree state

Run:

```bash
git status --short
git branch --show-current
git worktree list --porcelain
```

Do not overwrite, delete, reset, or clean user changes.

## Step 4: Prepare task branch

Create or switch to a task branch based on the latest remote base.

The branch must start from:

- `origin/{{dependency_branch}}` when dependency is provided
- otherwise `origin/{{base_ref}}`

Do not use a stale local base branch.

If reusing an existing task branch, rebase it onto the latest selected remote base unless explicitly told not to.

## Step 5: Read project context

Read relevant project files only after the branch/worktree is confirmed to be based on the latest remote base.

## Step 6: Report preflight

Before implementation, report:

- base ref,
- dependency branch (if used),
- `START_BASE_SHA`,
- current branch,
- whether the branch was created or reused,
- whether rebase was needed,
- any manual follow-up needed.

## Step 7: Implement task

Implement the requested task.
