# Electron sample target

This sample target provides the first Electron-based FileGate dialog exerciser for baseline open/save/folder scenarios.

It supports:

- `open_file_single`
- `open_file_multiple`
- `open_folder`
- `save_file_new`
- `filter_pdf_only`
- `filter_images_only`
- `filter_multiple_mime_types`
- `extension_auto_append_on_save`
- `wrong_extension_selected`
- `cancel_open_dialog`
- `cancel_save_dialog`
- `open_dialog_multiple_times`
- `open_after_app_restart`
- `persistent_access_after_restart`
- `revoked_access_behavior`
- `timeout_when_dialog_not_closed`

The app emits result JSON compatible with the required fields in [`docs/result-schema.md`](../../docs/result-schema.md).

## Files

- `package.json` — Electron package metadata and start script
- `main.js` — sample target entrypoint and dialog/result orchestration
- `preload.js` — minimal preload bridge
- `renderer.js` — minimal renderer bootstrap

## Install

From the repository root:

```bash
cd samples/electron
npm install
```

## Invocation contract

Run the sample app with:

```bash
cd samples/electron
npm start -- --scenario /absolute/path/to/scenario.json --output /absolute/path/to/result.json
```

If `--output` is omitted, the app writes to:

```text
samples/electron/out/<case-id>.result.json
```

The program prints the final result file path to stdout.

## Scenario input contract

The scenario format mirrors the Python Tkinter sample target:

- top-level `case`, optional `dialog`, optional `expectation`, optional `simulation`
- `simulation.enabled=true` allows deterministic non-interactive runs
- known case IDs infer dialog types automatically
- the runner may invoke the target multiple times for a single FileGate case and provides step metadata in `orchestration`

Supported dialog types:

- `open_file`
- `open_files`
- `open_folder`
- `save_file`
- `probe_resource`

Supported dialog fields:

- `title`
- `initialdir`
- `initialfile`
- `defaultextension`
- `filetypes`
- `mustexist`

Additional simulation fields used by the stability/persistence cases:

- `probe_path`
- `persisted_access`
- `revoke_access`
- `sleep_before_result_seconds`

Additional orchestration metadata passed by the runner:

- `orchestration.mode`
- `orchestration.step_id`
- `orchestration.step_index`
- `orchestration.total_steps`

## Result behavior

- Successful selection returns `result.status = "pass"`.
- Expected cancellation returns `result.status = "pass"` and `result.error_code = "USER_CANCELLED"`.
- Unexpected cancellation returns `result.status = "fail"` and `result.error_code = "USER_CANCELLED"`.
- Selection-count mismatches return `result.status = "fail"` with structured notes.
- Filter-oriented cases add structured notes describing configured filters, intended filter selection, and whether the returned extension matched the expected filter set.
- Save-extension cases add structured notes describing whether the configured extension was auto-appended, preserved, or overridden.
- Interactive native dialog results may include notes documenting platform/backend differences.
- `returned_resource_type` is currently `path` for baseline Electron cases.
- Persistence probe steps may return `warn` + `PERSISTENCE_DENIED` and revocation probe steps may return `manual_required` + `ACCESS_REVOKED`.

## Known differences

Electron delegates to native dialog backends, so behavior may vary by platform, display server, or desktop environment. In particular, active-filter choice and save-extension auto-append behavior are not exposed as deterministic native API signals. When that happens, FileGate records best-effort observations from the returned path and surfaces the limitation in result notes rather than forcing a failure if schema compatibility is preserved.

## Extension points

- XDG Portal integration can be introduced by detecting sandbox/runtime conditions and routing dialog handling through portal-aware code paths.
- Additional desktop frameworks can reuse the same scenario/result contract to stay comparable with Tkinter and Electron outputs.