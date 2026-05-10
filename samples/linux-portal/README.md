# Linux portal sample target

This sample target provides the first FileGate-native Linux portal-focused execution path for Phase 3.

It currently supports the initial portal/sandbox subset:

- `flatpak_open_file_portal`
- `flatpak_save_file_portal`
- `portal_cancel_behavior`
- `portal_returns_uri_or_path`
- `sandbox_no_home_access_without_grant`

## Purpose

The target is intentionally portal-oriented rather than toolkit-oriented:

- it probes `org.freedesktop.portal.Desktop`
- it records explicit portal capability metadata
- it records explicit sandbox and Flatpak filesystem-grant metadata
- it preserves whether the observed resource was URI-backed or path-backed

## Current scope and limitation

This initial landing focuses on explicit capability detection and deterministic scenario coverage.

- **Simulation mode** is fully supported and is the recommended validation path for now.
- **Interactive mode** currently degrades explicitly with structured notes when a live Request/Response flow has not been implemented yet.

This is deliberate: known environment or implementation limitations are recorded in artifacts instead of hidden.

## Prerequisites

- Linux session with a D-Bus session bus
- `gdbus` available in `PATH`
- For meaningful portal probing: `org.freedesktop.portal.Desktop`
- For Flatpak-specific observations: running inside Flatpak and access to `/.flatpak-info`

## Invocation

```bash
python samples/linux-portal/app.py \
  --scenario /absolute/path/to/scenario.json \
  --output /absolute/path/to/result.json
```

## Scenario notes

The scenario contract matches the other bundled sample targets, plus Phase 3 context fields populated by the runner:

- `execution_context.portal`
- `execution_context.sandbox`
- `execution_context.portal_expected`
- `execution_context.sandbox_expected`

In simulation mode, the runner may supply:

- `simulation.selected_uri`
- `simulation.selected_path`
- `simulation.metadata_only`
- `simulation.cancel`

## Result notes

Results include structured notes for:

- portal capability state
- sandbox context and Flatpak filesystem grants
- URI-vs-path observations
- document portal mount detection
- explicit limitations or missing prerequisites

## Extension points

- implement a live FileChooser `OpenFile` / `SaveFile` Request/Response flow over D-Bus
- add persistence-oriented cases such as `xdg_document_portal_persistence`
- compare GNOME/KDE backend differences using the same artifact schema