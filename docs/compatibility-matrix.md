# Compatibility Matrix

## Purpose

Define the first FileGate compatibility-matrix layer introduced in roadmap Phase 4.

## Scope of the First Iteration

This iteration is intentionally conservative.

Included:

- aggregation of multiple completed runs,
- deterministic grouping across target and environment dimensions,
- publication-friendly static JSON, Markdown, and HTML output,
- explicit summary baseline instead of implied scoring,
- preservation of repeated-run observations for reproducibility.

Not included yet:

- weighted compatibility scoring,
- interactive dashboards,
- remote publication or hosted result browsing,
- target-category-specific scoring profiles.

## Input Model

The matrix consumes existing run artifacts:

- one or more run directories,
- each directory contains `run-summary.json`,
- each run summary points to per-case `result.json` files.

No separate target-specific aggregation format is introduced.

## Grouping Model

The first implementation supports these column grouping modes:

- `target-environment` — one column per target name and environment signature,
- `target` — one column per target name across repeated runs,
- `environment` — one column per environment signature across repeated runs.

Environment signatures are built from these canonical fields:

- `os`
- `distribution`
- `version`
- `desktop_environment`
- `session_type`
- `sandbox`

Callers may reduce that signature in the CLI by specifying a smaller field subset for grouping.

## Aggregation Payload

The matrix JSON payload contains:

- `schema_version`
- `report_format = "matrix-json"`
- `generated_at`
- `group_by`
- `environment_fields`
- `filters_applied`
- `baseline_policy`
- `input_run_count`
- `group_count`
- `total_cases`
- `source_run_directories`
- `runs`
- `groups`
- `cases`

### `runs`

`runs` is a normalized list of included source runs with:

- run metadata,
- projected target metadata,
- projected environment metadata,
- run-level status counts,
- warning count.

### `groups`

Each group contains:

- `group_id`
- human-readable `label`
- included `runs`
- distinct `targets`
- distinct `environments`
- `latest_run`
- `summary_baseline`

### `cases`

Each case row contains:

- `case_id`
- `case_name`
- `automation_level`
- ordered `cells`

Each cell is either:

- `null` when the case is missing from that group, or
- an aggregated case observation with:
  - `aggregated_status`
  - `latest_status`
  - `counts_by_status`
  - `resource_types`
  - `error_codes`
  - `reproducibility`
  - `observation_count`
  - `latest_observation`
  - aggregation notes when statuses/resource types diverge.

## First Baseline Policy

The first iteration deliberately avoids a weighted score.

### Cell Status Rule

- If all observations within a cell share the same status, that status is retained.
- If observations disagree, the derived cell status is `mixed`.

### Summary Buckets

- `compatible` → `pass`
- `caution` → `warn`
- `problematic` → `fail`, `timeout`, `blocked`
- `unavailable` → `skip`, `unsupported`, `manual_required`, `inconclusive`
- `mixed` → derived `mixed`
- `missing` → case absent from a group

### Reproducibility Signal

Repeated runs are treated as evidence, not noise.

- `consistent` means observations agree on status and resource type.
- `mixed` means the same group produced diverging observations across runs.

This makes reproducibility explicit without forcing a premature numeric score.

## CLI Usage

Examples:

```bash
filegate matrix-report \
  --run-dir runs/<run-a> \
  --run-dir runs/<run-b> \
  --format markdown
```

```bash
filegate matrix-report \
  --latest-sample-runs \
  --group-by target \
  --format json
```

```bash
filegate matrix-report \
  --latest-sample-runs \
  --group-by environment \
  --target-filter electron \
  --environment-filter sandbox=none \
  --format html
```

## Future Framework/Platform Handoff

Future targets should feed the matrix by continuing to emit standard FileGate run artifacts with:

- stable `target.name`,
- meaningful `target.version` where available,
- complete environment metadata,
- canonical `case.id` values shared with the registry,
- normalized result statuses,
- structured notes for known differences,
- accurate `returned_resource_type` values.

As long as new targets follow that contract, Phase 5 and Phase 6 work can plug into the matrix layer without changing the aggregation format.