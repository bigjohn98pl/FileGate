# Task ID

`POC-03`

## Objective

Create the first sample target (`python-tkinter`) capable of executing basic open/save/folder dialog scenarios and writing result JSON.

## Scope

- In scope:
  - sample app under `samples/python-tkinter/`
  - scenario input contract for sample app
  - result JSON output compatible with `docs/result-schema.md`
- Out of scope (non-goals):
  - advanced UI automation
  - multi-target orchestration

## Input Context

- `docs/test-cases.md` (dialog basics)
- `docs/result-schema.md`

## Preconditions

- `POC-01` and `POC-02` merged

## Git Workflow (Mandatory)

- Create branch: `task/poc-03-first-sample-target-tkinter`
- Open MR to main after completion and validation
- Wait for maintainer approval before merge

## Execution Steps

1. Scaffold `samples/python-tkinter/` app.
2. Implement scenario handling for open/save/folder/cancel.
3. Emit result JSON to predictable output path.

## Expected Artifacts

- `samples/python-tkinter/README.md`
- `samples/python-tkinter/app.py`

## Validation

- Run sample app in each supported scenario.
- Verify JSON fields map to schema requirements.

## Merge Request Checklist

- [ ] Branch is dedicated to this task.
- [ ] Validation output is attached in MR description.
- [ ] No unrelated files are modified.

## Acceptance Criteria (Definition of Done)

- [ ] Sample app executes dialog basics scenarios.
- [ ] JSON output validates against schema v0.1 required fields.
- [ ] Cancel behavior is explicitly encoded.

## Failure Handling

- If toolkit limitations appear, document behavior and mark known gaps in sample README.

## Handoff Notes

Document sample app invocation contract for runner integration.
