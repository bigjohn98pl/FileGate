# Electron sample target

This sample target provides the first Electron-based FileGate dialog exerciser for baseline open/save/folder scenarios.

It supports:

- `open_file_single`
- `open_file_multiple`
- `open_folder`
- `save_file_new`
- `cancel_open_dialog`
- `cancel_save_dialog`

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

Supported dialog types:

- `open_file`
- `open_files`
- `open_folder`
- `save_file`

Supported dialog fields:

- `title`
- `initialdir`
- `initialfile`
- `defaultextension`
- `filetypes`
- `mustexist`

## Result behavior

- Successful selection returns `result.status = "pass"`.
- Expected cancellation returns `result.status = "pass"` and `result.error_code = "USER_CANCELLED"`.
- Unexpected cancellation returns `result.status = "fail"` and `result.error_code = "USER_CANCELLED"`.
- Selection-count mismatches return `result.status = "fail"` with structured notes.
- Interactive native dialog results may include notes documenting platform/backend differences.
- `returned_resource_type` is currently `path` for baseline Electron cases.

## Known differences

Electron delegates to native dialog backends, so behavior may vary by platform, display server, or desktop environment. When that happens, record the difference in result notes rather than forcing a failure if schema compatibility is preserved.

## Extension points

- XDG Portal integration can be introduced by detecting sandbox/runtime conditions and routing dialog handling through portal-aware code paths.
- Additional desktop frameworks can reuse the same scenario/result contract to stay comparable with Tkinter and Electron outputs.