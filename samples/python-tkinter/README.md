# Python Tkinter sample target

This sample target provides the first FileGate-native dialog exerciser for basic open/save/folder scenarios.

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
- `filter_pdf_only` → `open_file`
- `filter_images_only` → `open_file`
- `filter_multiple_mime_types` → `open_file`
- `extension_auto_append_on_save` → `save_file`
- `wrong_extension_selected` → `save_file`
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
- `expected_selection_count` — optional exact number of selected paths expected
- `min_selection_count` — optional minimum number of selected paths expected
- `max_selection_count` — optional maximum number of selected paths expected

Default selection-count behavior:

- `open_file_single` expects exactly 1 selected path
- `open_file_multiple` expects at least 2 selected paths
- other supported cases do not enforce a selection count unless the scenario sets one explicitly

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
- Selection-count mismatches return `result.status = "fail"` with a diagnostic note.
- Expected cancellation returns `result.status = "pass"` and `result.error_code = "USER_CANCELLED"`.
- Unexpected cancellation returns `result.status = "fail"` and `result.error_code = "USER_CANCELLED"`.
- Filter-oriented cases add structured notes describing configured filters, intended filter selection, and whether the returned extension matched the expected filter set.
- Save-extension cases add structured notes describing whether the configured extension was auto-appended, preserved, or overridden.
- When native dialog APIs do not expose deterministic filter/extension state, the sample reports best-effort observations and records that limitation in result notes.
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
