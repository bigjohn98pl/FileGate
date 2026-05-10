# Finish Kanban Task and Open PR

Use this workflow when implementation is complete and you want to open a PR.

## Input

- base ref: `{{base_ref}}` (default `main`)
- optional dependency branch: `{{dependency_branch}}`
- validation command(s): `{{validation_commands}}`

## Safety constraints

- Remote `origin/{{base_ref}}` is the source of truth.
- Keep all PR preparation in the current task worktree.
- Do not run destructive commands (`git reset --hard`, `git clean -fdx`, worktree deletion).

## Step 1: Ensure task changes are committed

Ensure all intended changes are committed in the current task worktree.

If on detached HEAD, create a branch at current commit before continuing.

## Step 2: Sync remote refs

Run:

```bash
git fetch --prune origin
```

## Step 3: Resolve latest base SHA

If `dependency_branch` is provided:

```bash
git rev-parse origin/{{dependency_branch}}
```

Otherwise:

```bash
git rev-parse origin/{{base_ref}}
```

Store this as `LATEST_BASE_SHA_BEFORE_PR`.

## Step 4: Rebase task branch

Rebase onto the latest selected remote base:

- `git rebase origin/{{dependency_branch}}` (dependent task)
- `git rebase origin/{{base_ref}}` (default)

If conflicts occur, resolve carefully while preserving both:

- intended task changes,
- changes already present in selected remote base.

## Step 5: Validation

Use `{{validation_commands}}` if explicitly provided.

Otherwise run the standard FileGate validation suite:

```bash
python -m compileall filegate samples/python-tkinter
python -m unittest discover -s tests -v
node --check samples/electron/main.js
node --check samples/electron/preload.js
node --check samples/electron/renderer.js
```

## Step 6: Push and create PR

Push branch with upstream:

```bash
git push -u origin <task-branch>
```

Create PR with `gh` using a structured description:

```bash
gh pr create \
  --base {{base_ref}} \
  --head <task-branch> \
  --title "<prefix>: <short description>" \
  --body "## Summary
<what this PR does and why>

## What changed
- <bullet per meaningful change>

## Validation
- <commands run and their results>"
```

If PR for same base/head already exists, return existing URL instead of creating duplicate.

If blocked, report exact reason and provide exact manual commands.

## Step 7: Final report

Report:

- PR title,
- PR URL,
- base branch,
- head branch,
- base SHA used at task start (if known),
- latest base SHA before PR,
- whether rebase was performed,
- whether conflicts were resolved,
- validation result,
- any follow-up needed.
