# Python Tkinter sample target

This sample target provides the first FileGate-native dialog exerciser for basic open/save/folder scenarios.

It supports:

- `open_file_single`
- `open_file_multiple`
- `open_folder`
- `save_file_new`
- `save_file_overwrite`
- `cancel_open_dialog`
- `cancel_save_dialog`

The app emits result JSON compatible with the required fields in [`docs/result-schema.md`](../../docs/result-schema.md).

## Files

- `app.py` — sample target entrypoint
- `out/` — default output directory for result JSON

## Invocation contract

Run the sample app with:

```bash
python samples/python-tkinter/app.py --scenario /absolute/path/to/scenario.json
```

Optional explicit result path:

```bash
python samples/python-tkinter/app.py \
  --scenario /absolute/path/to/scenario.json \
  --output /absolute/path/to/result.json
```

If `--output` is omitted, the app writes to:

```text
samples/python-tkinter/out/<case-id>.result.json
```

The program prints the final result file path to stdout.

## Scenario input contract

The scenario file is JSON.

### Minimal example

```json
{
  "case": {
    "id": "open_file_single"
  }
}
```

### Recommended full example

```json
{
  "run_id": "2026-05-09T12-00-00Z-linux-kde-python-tkinter",
  "platform": {
    "os": "linux",
    "distribution": "Fedora",
    "version": "43",
    "desktop_environment": "KDE Plasma",
    "session_type": "wayland",
    "sandbox": "none"
  },
  "case": {
    "id": "save_file_new",
    "name": "Save file new",
    "automation_level": "semi_automatic"
  },
  "dialog": {
    "type": "save_file",
    "title": "Choose where to save the sample file",
    "initialdir": "/tmp",
    "initialfile": "example.txt",
    "defaultextension": ".txt",
    "filetypes": [
      ["Text files", "*.txt"],
      ["All files", "*.*"]
    ]
  },
  "expectation": {
    "cancel_is_expected": false
  }
}
```

## Supported scenario fields

### Top-level

- `run_id` — optional; auto-generated if omitted
- `platform` — optional object; missing values are inferred from the environment when possible
- `case` — required object
- `dialog` — optional for known `case.id` values, otherwise required
- `expectation` — optional object
- `simulation` — optional object for non-interactive execution

### `case`

Required:

- `id`

Optional:

- `name`
- `automation_level` (`automatic`, `semi_automatic`, `manual`)

Known case IDs map automatically to default dialog types:

- `open_file_single` → `open_file`
- `open_file_multiple` → `open_files`
- `open_folder` → `open_folder`
- `save_file_new` → `save_file`
- `save_file_overwrite` → `save_file`
- `cancel_open_dialog` → `open_file`
- `cancel_save_dialog` → `save_file`

### `dialog`

Supported fields:

- `type` — one of `open_file`, `open_files`, `open_folder`, `save_file`
- `title`
- `initialdir`
- `initialfile`
- `defaultextension`
- `filetypes` — array of `[label, pattern]`
- `mustexist` — relevant for folder/open selection behavior

### `expectation`

- `cancel_is_expected` — boolean; useful for cancel-specific cases

### `simulation`

Simulation mode exists for runner integration, CI, and headless validation where native dialogs cannot be shown.

Fields:

- `enabled` — boolean
- `cancel` — boolean
- `selected_path` — single selected path for `open_file`, `open_folder`, or `save_file`
- `selected_paths` — array of paths for `open_files`

Example:

```json
{
  "case": {
    "id": "cancel_open_dialog"
  },
  "expectation": {
    "cancel_is_expected": true
  },
  "simulation": {
    "enabled": true,
    "cancel": true
  }
}
```

## Result behavior

The output JSON always includes the required top-level keys:

- `schema_version`
- `run_id`
- `platform`
- `target`
- `case`
- `result`

Result mapping notes:

- Successful selection returns `result.status = "pass"`.
- Expected cancellation returns `result.status = "pass"` and `result.error_code = "USER_CANCELLED"`.
- Unexpected cancellation returns `result.status = "fail"` and `result.error_code = "USER_CANCELLED"`.
- Headless or unavailable Tk backends return `result.status = "unsupported"` or `fail` with an explanatory error code.
- `returned_resource_type` is `path` when a path is returned and `unknown` when nothing is selected.

## Validation examples

### Open file single

```json
{
  "case": {"id": "open_file_single"},
  "simulation": {
    "enabled": true,
    "selected_path": "/tmp/example.txt"
  }
}
```

### Open multiple files

```json
{
  "case": {"id": "open_file_multiple"},
  "simulation": {
    "enabled": true,
    "selected_paths": ["/tmp/a.txt", "/tmp/b.txt"]
  }
}
```

### Open folder

```json
{
  "case": {"id": "open_folder"},
  "simulation": {
    "enabled": true,
    "selected_path": "/tmp"
  }
}
```

### Save file

```json
{
  "case": {"id": "save_file_new"},
  "simulation": {
    "enabled": true,
    "selected_path": "/tmp/output.txt"
  }
}
```

### Cancel save

```json
{
  "case": {"id": "cancel_save_dialog"},
  "expectation": {
    "cancel_is_expected": true
  },
  "simulation": {
    "enabled": true,
    "cancel": true
  }
}
```

## Known gaps

- Real dialog automation is intentionally out of scope for this POC.
- In headless environments without a display server, interactive Tk dialogs may be unavailable. Use `simulation.enabled=true` for validation in CI or agent environments.
- Exact dialog visuals and some platform-specific behavior may vary by operating system and desktop environment.
