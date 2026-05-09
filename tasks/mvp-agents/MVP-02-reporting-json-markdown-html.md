# Task ID

`MVP-02`

## Objective

Implement reporting modules for JSON aggregation, Markdown summary, and initial static HTML output.

## Scope

- In scope:
  - `filegate/reporting/json.py`
  - `filegate/reporting/markdown.py`
  - `filegate/reporting/html.py`
  - CLI report command integration
- Out of scope (non-goals):
  - advanced interactive dashboards
  - historical trend analytics

## Input Context

- `docs/result-schema.md`
- `docs/roadmap.md` (Phase 1/2)

## Preconditions

- `MVP-01` merged

## Git Workflow (Mandatory)

- Create branch: `task/mvp-02-reporting-json-markdown-html`
- Open MR to main after completion and validation
- Wait for maintainer approval before merge

## Execution Steps

1. Implement JSON aggregation from run outputs.
2. Implement Markdown summary renderer for README-friendly output.
3. Implement minimal static HTML report renderer.
4. Wire `filegate report --format {json|markdown|html}`.

## Expected Artifacts

- `filegate/reporting/json.py`
- `filegate/reporting/markdown.py`
- `filegate/reporting/html.py`
- updates in CLI and/or runner interfaces

## Validation

- Generate all three formats from a sample run directory.
- Verify Markdown table structure and HTML readability.

## Merge Request Checklist

- [ ] Branch is dedicated to this task.
- [ ] Validation output is attached in MR description.
- [ ] No unrelated files are modified.

## Acceptance Criteria (Definition of Done)

- [ ] All three report formats are generated successfully.
- [ ] Reports are consistent with source run data.
- [ ] CLI format switch behaves predictably.

## Failure Handling

- If source results are incomplete, emit explicit warnings rather than silently dropping cases.

## Handoff Notes

Describe report contract expected by compatibility matrix tasks.
