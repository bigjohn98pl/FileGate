# Task ID

`MVP-01`

## Objective

Implement the core runner flow and initial case registry so FileGate can execute selected cases against a target and persist structured outputs.

## Scope

- In scope:
  - `filegate/runner.py` core orchestration
  - `filegate/cases.py` case registry for MVP baseline
  - timeout/cancellation handling in runner
  - JSON result persistence for each case run
- Out of scope (non-goals):
  - HTML report generation
  - full target matrix aggregation

## Input Context

- `docs/test-cases.md`
- `docs/result-schema.md`
- `docs/file-access-behavior-spec-0.1.md`

## Preconditions

- `POC-01`, `POC-02`, and `POC-03` merged

## Git Workflow (Mandatory)

- Create branch: `task/mvp-01-runner-core-case-registry`
- Open MR to main after completion and validation
- Wait for maintainer approval before merge

## Execution Steps

1. Define case registry model and seed MVP case subset.
2. Implement runner lifecycle (prepare → execute target → collect output → persist result).
3. Add timeout and cancellation semantics aligned with status vocabulary.

## Expected Artifacts

- `filegate/runner.py`
- `filegate/cases.py`
- optional helper modules for execution contracts

## Validation

- Execute runner against Tkinter sample target for at least 3 core cases.
- Verify persisted outputs conform to required result fields.

## Merge Request Checklist

- [ ] Branch is dedicated to this task.
- [ ] Validation output is attached in MR description.
- [ ] No unrelated files are modified.

## Acceptance Criteria (Definition of Done)

- [ ] Runner executes selected cases deterministically.
- [ ] Timeout/cancel behavior maps to valid status values.
- [ ] Each case run writes JSON output with schema v0.1 required fields.

## Failure Handling

- If sample app output is inconsistent, add explicit normalization layer and document assumptions.

## Handoff Notes

List runner interfaces expected by report generation tasks.
