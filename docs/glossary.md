# Glossary

## Purpose

This glossary defines the canonical terms used across FileGate documentation.

## Terms

- **Target**: A concrete technology under test (for example Electron, Tkinter, GTK, Qt, XDG Portal direct integration).
- **Case**: A single test scenario with explicit preconditions, steps, expected behavior, and output requirements.
- **Run**: One execution instance of one or more cases against a target in a specific environment.
- **Environment**: Runtime context (OS, distribution/version, desktop environment, session type, sandbox, backend).
- **Automation level**: How much human interaction a case requires (`automatic`, `semi_automatic`, `manual`).
- **Resource type**: Returned file-access representation (`path`, `uri`, `handle`, `unknown`).
- **Permission grant**: User-mediated authorization allowing access to a selected resource.
- **Persistence**: Whether access remains valid across app restart/session restart.
- **Portal backend**: System intermediary layer for sandboxed resource access (for example XDG Desktop Portal).
- **Compatibility matrix**: Aggregated comparative view of case outcomes across environments and targets.
- **Conformance**: Degree to which behavior matches expected semantics defined by FileGate specs.
- **Known difference**: Platform-specific behavior that is valid but not identical to other platforms.
- **Regression**: Behavior change from a previously accepted result, typically detected by repeated runs.
