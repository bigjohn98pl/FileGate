# Task ID

`MVP-03`

## Objective

Add the first Electron sample target and establish a baseline comparison against the Python Tkinter target.

## Scope

- In scope:
  - `samples/electron/` minimal app
  - target integration in `filegate/targets/electron.py`
  - run support for open/save/folder baseline cases
  - baseline comparison output for two targets
- Out of scope (non-goals):
  - full desktop-environment matrix
  - Flatpak packaging

## Input Context

- `docs/test-cases.md`
- `docs/result-schema.md`
- `docs/roadmap.md` (Phase 2)

## Preconditions

- `MVP-01` and `MVP-02` merged

## Git Workflow (Mandatory)

- Create branch: `task/mvp-03-electron-target-compat-baseline`
- Open MR to main after completion and validation
- Wait for maintainer approval before merge

## Execution Steps

1. Scaffold Electron sample app with IPC/result output contract.
2. Implement Electron target adapter in FileGate.
3. Execute baseline case subset on both Tkinter and Electron targets.
4. Produce comparison report artifacts.

## Expected Artifacts

- `samples/electron/README.md`
- `samples/electron/package.json`
- `samples/electron/main.js`
- `samples/electron/preload.js`
- `samples/electron/renderer.js`
- `filegate/targets/electron.py`

## Validation

- Run baseline cases for both targets.
- Verify output schema compatibility.
- Verify report shows per-target results side-by-side.

## Merge Request Checklist

- [ ] Branch is dedicated to this task.
- [ ] Validation output is attached in MR description.
- [ ] No unrelated files are modified.

## Acceptance Criteria (Definition of Done)

- [ ] Electron target executes MVP baseline cases.
- [ ] Result output matches schema v0.1 requirements.
- [ ] Comparison report includes both Python and Electron targets.

## Failure Handling

- If native dialog behavior differs by platform, record as known difference with notes instead of forcing failure.

## Handoff Notes

Document extension points for XDG Portal and additional frameworks.
