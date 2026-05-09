# Problem Statement

## Purpose

File access looks simple in UI but is complex across platform and framework boundaries. FileGate exists to measure, compare, and document that behavior.

## Core Problem

The same user flow can produce different technical outcomes depending on:

- operating system,
- desktop environment,
- framework,
- sandbox/permission model,
- portal/dialog backend,
- filesystem and storage provider.

This creates real product risks:

- inconsistent path/URI/handle behavior,
- non-persistent access after restart,
- non-uniform cancel/error semantics,
- sandbox visibility mismatches,
- framework portability regressions.

## Scope

FileGate focuses on user-mediated file access behavior:

- open file dialog,
- save file dialog,
- folder picker,
- path/URI/handle return types,
- permission grants and revocation,
- sandbox and portal interaction,
- edge cases (Unicode, symlinks, long paths, permissions, cloud placeholders).

## Non-Goals

FileGate is not:

- a replacement for native dialog APIs,
- a new portal/sandbox implementation,
- a universal UI toolkit,
- a production file-picker abstraction layer.

## Mission

Build a practical conformance toolkit composed of:

- test cases,
- sample targets,
- diagnostics,
- structured results,
- compatibility matrix,
- behavior specification baseline.

## Initial Strategy

MVP-first and Linux-first:

1. establish test semantics,
2. run local Linux targets,
3. generate machine-readable reports,
4. compare behavior across frameworks,
5. scale to additional targets and platforms.
