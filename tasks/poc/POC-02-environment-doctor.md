# Task ID

`POC-02`

## Objective

Implement the first version of `filegate doctor` to detect core runtime environment metadata.

## Scope

- In scope:
  - detect OS, distribution, version
  - detect desktop environment and session type (Wayland/X11)
  - detect sandbox context (Flatpak/Snap/none)
  - detect Python version and required runtime dependencies
- Out of scope (non-goals):
  - deep hardware diagnostics
  - remote telemetry

## Input Context

- `docs/roadmap.md` (Phase 1)
- `docs/result-schema.md` (platform structure alignment)

## Preconditions

- `POC-01` merged

## Git Workflow (Mandatory)

- Create branch: `task/poc-02-environment-doctor`
- Open MR to main after completion and validation
- Wait for maintainer approval before merge

## Execution Steps

1. Create `filegate/environment.py` with data model and detection helpers.
2. Implement CLI `doctor` command using structured output.
3. Add graceful fallback behavior when metadata cannot be detected.

## Expected Artifacts

- `filegate/environment.py`
- update `filegate/cli.py`

## Validation

- `python -m filegate.cli doctor`
- run under at least one Wayland/X11 environment and verify fields

## Merge Request Checklist

- [ ] Branch is dedicated to this task.
- [ ] Validation output is attached in MR description.
- [ ] No unrelated files are modified.

## Acceptance Criteria (Definition of Done)

- [ ] `doctor` outputs the requested metadata fields.
- [ ] Missing values are represented explicitly (not hidden failures).
- [ ] Command exits with stable status code on success.

## Failure Handling

- If environment probes are platform-specific, isolate Linux-first logic with explicit TODO markers.

## Handoff Notes

Document which fields are reliable vs best-effort for downstream reporting tasks.
