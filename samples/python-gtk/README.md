# Python GTK sample target

This sample target adds a GTK-based framework implementation for FileGate Phase 5 framework expansion.

It supports the current runnable MVP case subset:

- `open_file_single`
- `open_file_multiple`
- `open_folder`
- `save_file_new`
- `cancel_open_dialog`
- `cancel_save_dialog`

The app emits result JSON compatible with the required fields in [`docs/result-schema.md`](../../docs/result-schema.md).

## Why GTK was chosen next

The roadmap Phase 5 candidate list names both Qt and GTK as preferred next framework targets.

In this repository environment, GTK was the most practical next target because:

- Python `gi` / PyGObject is already available,
- GTK 4 bindings are installed and working,
- the target can be implemented without adding new Python package dependencies to the project itself.

Qt remains a good future target, but in this environment it would first require choosing and provisioning a Python binding such as PyQt or PySide.

## Files

- `app.py` — sample target entrypoint
- `out/` — default output directory for result JSON

## Invocation contract

Run the sample app with:

```bash
python samples/python-gtk/app.py --scenario /absolute/path/to/scenario.json
```

Optional explicit result path:

```bash
python samples/python-gtk/app.py \
  --scenario /absolute/path/to/scenario.json \
  --output /absolute/path/to/result.json
```

If `--output` is omitted, the app writes to:

```text
samples/python-gtk/out/<case-id>.result.json
```

The program prints the final result file path to stdout.

## Scenario input contract

The scenario format mirrors the existing Python Tkinter and Electron sample targets:

- top-level `case`, optional `dialog`, optional `expectation`, optional `simulation`
- known case IDs infer dialog types automatically
- `simulation.enabled=true` supports deterministic headless validation

Supported dialog types:

- `open_file`
- `open_files`
- `open_folder`
- `save_file`

Supported dialog fields:

- `title`
- `initialdir`
- `initialfile`
- `defaultextension` — accepted for schema parity, though GTK save naming is primarily driven by `initialfile`
- `filetypes`

## Result behavior

- Successful selection returns `result.status = "pass"`.
- Expected cancellation returns `result.status = "pass"` and `result.error_code = "USER_CANCELLED"`.
- Unexpected cancellation returns `result.status = "fail"` and `result.error_code = "USER_CANCELLED"`.
- Selection-count mismatches return `result.status = "fail"` with structured notes.
- Simulation mode adds a `SIMULATED` note for comparability with other targets.
- Interactive GTK runs add a `GTK_NATIVE_DIALOG` note documenting backend variability.

## Known differences relative to existing targets

- Compared with Tkinter, GTK uses GTK 4 `FileDialog` APIs, which may delegate to portal-aware or desktop-native backends depending on the session.
- Compared with Electron, this target is pure Python and has no Node/npm preparation step.
- In headless environments, interactive GTK dialogs are not expected to work; use FileGate simulation mode for validation.
- GTK save dialogs may interpret initial naming hints slightly differently from Electron or Tkinter depending on backend and desktop environment.

## Prerequisites

- Python `3.11+`
- PyGObject with GTK 4 bindings available as `gi`
- For interactive runs: an active graphical session (`DISPLAY` or `WAYLAND_DISPLAY`)

## Extension points

- A future portal-focused GTK variant can record whether the backend routed through XDG Desktop Portal.
- Remaining roadmap candidates can reuse this sample’s scenario/result helpers and preparation pattern.
- Qt can follow the same adapter pattern once a repository-supported Python binding is chosen.