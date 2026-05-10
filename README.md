# FileGate

FileGate is a cross-platform file access conformance toolkit.

It tests how operating systems, desktop environments, and application frameworks handle user-mediated file access (open/save dialogs, folder pickers, paths, URIs, file handles, sandbox permissions, and related edge cases).

## Documentation

This project uses documentation as the primary source of truth before implementation.

- [`docs/problem-statement.md`](docs/problem-statement.md) — problem framing, scope, and mission
- [`docs/glossary.md`](docs/glossary.md) — shared terminology
- [`docs/file-access-behavior-spec-0.1.md`](docs/file-access-behavior-spec-0.1.md) — behavior specification v0.1
- [`docs/test-cases.md`](docs/test-cases.md) — test model and case catalog
- [`docs/edge-cases.md`](docs/edge-cases.md) — known edge-case taxonomy
- [`docs/result-schema.md`](docs/result-schema.md) — canonical JSON result schema
- [`docs/related-projects.md`](docs/related-projects.md) — ecosystem references
- [`docs/roadmap.md`](docs/roadmap.md) — phased delivery plan

## Workflow

1. Define and refine documents in `docs/`.
2. Derive implementation work items from documentation.
3. Implement and validate the derived work in the codebase.
