# Sync Base Before Integrating Task Changes

Use this helper workflow before cherry-picking or integrating task changes into a base worktree.

## Input

- base ref: `{{base_ref}}` (default `main`)
- base worktree path: `{{base_worktree_path}}`

## Step 1: Fetch latest remote state

Run:

```bash
git -C {{base_worktree_path}} fetch --prune origin
git -C {{base_worktree_path}} status --short
```

## Step 2: Fast-forward local base safely

If base worktree has no uncommitted changes, update base with:

```bash
git -C {{base_worktree_path}} pull --ff-only origin {{base_ref}}
```

If there are uncommitted changes, stash first, then pull with `--ff-only`, then restore stash if needed.

## Step 3: Verify base freshness

Run:

```bash
git -C {{base_worktree_path}} rev-parse HEAD
git -C {{base_worktree_path}} rev-parse origin/{{base_ref}}
```

These values must match before cherry-picking or integrating task commits.

## Step 4: Integrate task commits

Only after verification, integrate task commits (for example by `git cherry-pick <sha>`).
