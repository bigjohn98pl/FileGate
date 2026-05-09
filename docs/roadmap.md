# Roadmap

## Purpose

Define phased delivery for FileGate from research baseline to multi-platform conformance toolkit.

## Phase 0 — Research and Documentation

### Goals

- formalize problem framing,
- define behavior spec baseline,
- define case catalog,
- define canonical result schema.

### Exit Criteria

- docs set is coherent and versioned,
- implementation backlog can be derived directly from docs.

## Phase 1 — Local Linux MVP

### Goals

- Python CLI scaffold,
- environment detection (`doctor`),
- initial test data preparation,
- first Python sample target,
- JSON + Markdown reporting.

### Exit Criteria

- at least one target executes core dialog cases end-to-end,
- structured run output is generated and reproducible.

## Phase 2 — Electron Target

### Goals

- Electron sample target,
- parity cases for open/save/folder,
- comparative output vs Python target,
- initial HTML report.

### Exit Criteria

- at least two targets can be compared under same case catalog.

## Phase 3 — XDG Portal / Flatpak

### Goals

- portal-focused target path,
- sandbox execution scenarios,
- KDE/GNOME behavior comparison.

### Exit Criteria

- portal-specific behavior is captured with explicit metadata and notes.

## Phase 4 — Compatibility Matrix

### Goals

- aggregation model,
- scoring policy,
- static report publication format.

### Exit Criteria

- matrix view supports filtering by environment and target dimensions.

## Phase 5 — Framework Expansion

### Candidate Targets

- Qt,
- GTK,
- Tauri,
- Native File Dialog Extended,
- tinyfiledialogs.

### Exit Criteria

- additional targets follow same schema/case semantics without ad-hoc formats.

## Phase 6 — Windows and macOS

### Goals

- platform onboarding,
- path/URI/handle semantics comparison,
- platform-specific permission model cases.

### Exit Criteria

- baseline cross-platform comparison available for at least one target family.

## Phase 7 — Spec Maturity and Upstream Issues

### Goals

- evolve behavior spec beyond v0.1,
- establish issue-reporting templates,
- produce high-quality upstream bug reports.

### Exit Criteria

- repeatable issue pipeline from FileGate evidence to upstream report.
