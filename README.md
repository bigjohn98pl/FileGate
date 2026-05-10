# FileGate

FileGate is a cross-platform file access conformance toolkit.

It tests how operating systems, desktop environments, and application frameworks handle user-mediated file access (open/save dialogs, folder pickers, paths, URIs, file handles, sandbox permissions, and related edge cases).

## What FileGate can do today

The current repository already includes a working CLI and sample targets for running a small MVP case set.

Today, FileGate can:

- inspect your local environment with `doctor`
- list implemented cases with `list-cases`
- run cases against a target application using a documented scenario/result contract
- generate JSON, Markdown, and HTML reports from a run directory
- compare two completed runs side by side

The broader documentation in `docs/` describes a larger planned conformance surface. Not every case listed there is implemented in the CLI yet. The current runnable case set is the one returned by `filegate list-cases`.

## Prerequisites

- Python `3.11+`
- `pip` for installing the package locally
- For the bundled Electron sample: Node.js and npm
- For interactive desktop dialog testing: a graphical desktop session compatible with your target app

Current Python dependency:

- `click`

You can verify your local environment with:

```bash
filegate doctor
```

or, without installing a console script first:

```bash
python -m filegate.cli doctor
```

## Installation

From the repository root:

```bash
python -m pip install -e .
```

This installs the `filegate` CLI entrypoint defined by the project.

If you prefer not to install it yet, you can run the CLI directly with:

```bash
python -m filegate.cli --help
```

## CLI overview

The current CLI commands are:

- `filegate doctor`
- `filegate list-cases`
- `filegate list-targets`
- `filegate run`
- `filegate report`
- `filegate compare-runs`

Show help at any time with:

```bash
filegate --help
filegate run --help
```

## Implemented cases in the current MVP

At the time of writing, `list-cases` reports these runnable cases:

- `open_file_single`
- `open_file_multiple`
- `open_folder`
- `save_file_new`
- `cancel_open_dialog`
- `cancel_save_dialog`

These are currently marked as `semi_automatic` cases. In practice:

- the runner prepares a scenario for the target
- sample targets can execute those scenarios in simulation mode for deterministic validation
- real GUI behavior still depends on the target application and desktop environment

## Typical usage flow

### 1. Check your environment

```bash
filegate doctor
```

This prints a JSON report with:

- detected platform metadata
- Python version
- required dependency availability
- reliability notes for detected fields

This is useful before running tests, especially on different desktop environments or sandbox setups.

### 2. Discover available cases

```bash
filegate list-cases
```

Example output:

```text
open_file_single    semi_automatic    Open file single
open_file_multiple  semi_automatic    Open file multiple
open_folder         semi_automatic    Open folder
save_file_new       semi_automatic    Save file new
cancel_open_dialog  semi_automatic    Cancel open dialog
cancel_save_dialog  semi_automatic    Cancel save dialog
```

Use this command as the source of truth for what the current implementation can execute.

### 3. Discover bundled target presets

```bash
filegate list-targets
```

Example output:

```text
python-tkinter  Bundled Python Tkinter sample target.
electron        Bundled Electron sample target.
```

### 4. Run one or more cases against a target

`run` supports two modes:

1. **Preset mode (recommended for first run)**
2. **Advanced custom command mode**

It also supports execution mode selection:

- `--mode auto` (default) — uses interactive dialogs when GUI session is available, otherwise simulation
- `--mode interactive` — force real dialog interaction
- `--mode simulation` — force deterministic non-interactive simulation

#### Preset mode (recommended)

Run the bundled Tkinter sample:

```bash
filegate run python-tkinter --mode interactive --output-dir runs
```

Run the bundled Electron sample:

```bash
filegate run electron --mode interactive --output-dir runs
```

If you omit `--case-id`, FileGate runs all currently implemented cases.

You can still limit cases:

```bash
filegate run python-tkinter \
  --mode interactive \
  --case-id open_file_single \
  --case-id open_folder
```

#### Advanced custom mode

The generic `run` command launches a target command and passes it:

- `--scenario <path-to-scenario.json>`
- `--output <path-to-result.json>`

That means your target must implement FileGate's scenario/result contract.

General form:

```bash
filegate run \
  [<preset-target-id>] \
  [--mode auto|interactive|simulation] \
  [--case-id <case-id>]... \
  [--output-dir runs] \
  [--timeout-seconds 10]
```

Custom target form:

```bash
filegate run \
  --target-name <logical-name> \
  --target-command '<command used to start the app>' \
  --sample-app <identifier-used-in-results> \
  [--case-id <case-id>]... \
  [--output-dir runs] \
  [--timeout-seconds 10] \
  [--mode auto|interactive|simulation] \
  [--working-directory /absolute/path]
```

#### Example: run a custom command-compatible target

This repository includes `samples/python-tkinter/app.py`, which follows the required target contract.

```bash
filegate run \
  --target-name my-target \
  --target-command 'python3 samples/python-tkinter/app.py' \
  --sample-app samples/python-tkinter \
  --mode simulation \
  --case-id open_file_single
```

### 5. Generate a report from a completed run

Each run creates a run directory containing a `run-summary.json` file. Use that run directory with `report`.

Print a Markdown report to stdout:

```bash
filegate report --run-dir runs/<run-id> --format markdown
```

Write an HTML report to a file:

```bash
filegate report \
  --run-dir runs/<run-id> \
  --format html \
  --output reports/<run-id>.html
```

Supported formats:

- `json`
- `markdown`
- `html`

### 6. Compare two runs

If you have two run directories, you can compare them directly:

```bash
filegate compare-runs \
  --left-run-dir runs/<left-run-id> \
  --right-run-dir runs/<right-run-id> \
  --format markdown
```

Or write an HTML comparison report:

```bash
filegate compare-runs \
  --left-run-dir runs/<left-run-id> \
  --right-run-dir runs/<right-run-id> \
  --format html \
  --output reports/comparison.html
```

## Bundled sample targets

### Python Tkinter sample

Location:

- [`samples/python-tkinter`](samples/python-tkinter)

This sample is useful as a simple FileGate-compatible target. It supports baseline open/save/folder scenarios and can operate in simulation mode, which makes it a good reference target for validating the FileGate runner itself.

See also:

- [`samples/python-tkinter/README.md`](samples/python-tkinter/README.md)

### Electron sample

Location:

- [`samples/electron`](samples/electron)

Install its dependencies first:

```bash
cd samples/electron
npm install
```

Then run it with the preset target:

```bash
filegate run electron --mode interactive --case-id open_file_single --output-dir runs
```

This command uses the bundled Electron sample target automatically.

Notes:

- it depends on npm/Electron being installed successfully in `samples/electron`
- behavior may vary across desktop backends because Electron delegates to native dialog handling

See also:

- [`samples/electron/README.md`](samples/electron/README.md)

## Run output layout

By default, runs are written under `runs/`.

Each invocation creates a unique run directory:

```text
runs/
  <run-id>/
    run-summary.json
    <case-id>/
      scenario.json
      stdout.log
      stderr.log
      result.json
```

What these files are for:

- `run-summary.json` — top-level run metadata plus one record per case
- `scenario.json` — the exact scenario passed to the target
- `stdout.log` / `stderr.log` — captured target process output
- `result.json` — normalized case result payload

The report command reads from the run directory, specifically expecting `run-summary.json` to exist there.

## Example workflows

### Workflow A: sanity-check the installation

```bash
filegate doctor
filegate list-cases
```

Use this when you first clone the repo or switch to another machine/session.

### Workflow B: run a single case and inspect the result

```bash
filegate run python-tkinter \
  --mode interactive \
  --case-id open_file_single \
  --output-dir runs

filegate report --run-dir runs/<run-id> --format markdown
```

Expected outcome:

- FileGate prints the generated run ID
- FileGate prints the path to `run-summary.json`
- the case directory contains `scenario.json`, logs, and `result.json`

### Workflow C: generate a shareable HTML report

```bash
filegate report \
  --run-dir runs/<run-id> \
  --format html \
  --output reports/<run-id>.html
```

Expected outcome:

- a standalone HTML file is written to your chosen `--output` path

### Workflow D: compare two environments or two targets

```bash
filegate compare-runs \
  --left-run-dir runs/<run-id-a> \
  --right-run-dir runs/<run-id-b> \
  --format markdown
```

This is useful for comparing:

- two desktop environments
- two app frameworks
- two versions of the same target

## Notes on current implementation status

- The CLI is real and runnable now.
- The current implemented case registry is intentionally small.
- The broader catalog in [`docs/test-cases.md`](docs/test-cases.md) includes planned cases that are not yet exposed by `list-cases`.
- The `run` command only works with targets that accept FileGate's `--scenario` and `--output` arguments and emit compatible result JSON.
- Sample targets support both simulation and interactive modes. Use `--mode interactive` when you want to manually interact with native dialogs, and `--mode simulation` for deterministic/headless validation.

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
