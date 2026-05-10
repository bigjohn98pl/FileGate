"""Compatibility-matrix aggregation and rendering for FileGate runs."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from html import escape
import json
from pathlib import Path
from typing import Any, Iterable

from filegate.reporting.json import build_report_payload

MATRIX_SCHEMA_VERSION = "0.1"
MATRIX_GROUP_BY_CHOICES = ("target-environment", "target", "environment")
MATRIX_ENVIRONMENT_FIELDS = (
    "os",
    "distribution",
    "version",
    "desktop_environment",
    "session_type",
    "sandbox",
)
MATRIX_PROBLEMATIC_STATUSES = {"fail", "timeout", "blocked"}
MATRIX_UNAVAILABLE_STATUSES = {"skip", "unsupported", "manual_required", "inconclusive"}


def build_matrix_payload(
    run_dirs: Iterable[Path],
    *,
    group_by: str = "target-environment",
    environment_fields: Iterable[str] | None = None,
    target_filters: Iterable[str] | None = None,
    environment_filters: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build a compatibility-matrix payload from multiple FileGate runs."""
    normalized_group_by = _normalize_group_by(group_by)
    normalized_environment_fields = _normalize_environment_fields(environment_fields)
    normalized_target_filters = {value.strip().casefold() for value in (target_filters or []) if value.strip()}
    normalized_environment_filters = _normalize_environment_filters(environment_filters or {})

    prepared_runs = [_prepare_run_report(run_dir) for run_dir in _normalize_run_dirs(run_dirs)]
    included_runs = [
        run
        for run in prepared_runs
        if _matches_filters(
            run,
            target_filters=normalized_target_filters,
            environment_filters=normalized_environment_filters,
        )
    ]
    if not included_runs:
        raise ValueError("No FileGate runs matched the requested matrix filters.")

    included_runs.sort(key=_run_sort_key)
    case_catalog = _build_case_catalog(included_runs)
    groups = _build_groups(
        included_runs,
        group_by=normalized_group_by,
        environment_fields=normalized_environment_fields,
    )

    case_rows: list[dict[str, Any]] = []
    group_summaries: list[dict[str, Any]] = []
    all_case_ids = [entry["case_id"] for entry in case_catalog]
    cells_by_group_case: dict[tuple[str, str], dict[str, Any]] = {}

    for group in groups:
        group_summary = _build_group_summary(group, all_case_ids)
        group_summaries.append(group_summary)
        for cell in group_summary["case_cells"]:
            cells_by_group_case[(group_summary["group_id"], cell["case_id"])] = cell

    for case_entry in case_catalog:
        row_cells: list[dict[str, Any] | None] = []
        for group_summary in group_summaries:
            row_cells.append(cells_by_group_case.get((group_summary["group_id"], case_entry["case_id"])))
        case_rows.append(
            {
                "case_id": case_entry["case_id"],
                "case_name": case_entry["case_name"],
                "automation_level": case_entry["automation_level"],
                "cells": row_cells,
            }
        )

    return {
        "schema_version": MATRIX_SCHEMA_VERSION,
        "report_format": "matrix-json",
        "generated_at": datetime.now(UTC).isoformat(),
        "group_by": normalized_group_by,
        "environment_fields": list(normalized_environment_fields),
        "filters_applied": {
            "targets": sorted(normalized_target_filters),
            "environment": dict(sorted(normalized_environment_filters.items())),
        },
        "baseline_policy": _baseline_policy_payload(),
        "input_run_count": len(included_runs),
        "group_count": len(group_summaries),
        "total_cases": len(case_rows),
        "source_run_directories": [run["source_run_directory"] for run in included_runs],
        "runs": [_project_run(run) for run in included_runs],
        "groups": [
            {
                "group_id": group_summary["group_id"],
                "label": group_summary["label"],
                "runs": group_summary["runs"],
                "targets": group_summary["targets"],
                "environments": group_summary["environments"],
                "latest_run": group_summary["latest_run"],
                "summary_baseline": group_summary["summary_baseline"],
            }
            for group_summary in group_summaries
        ],
        "cases": case_rows,
    }


def render_matrix_json_report(
    run_dirs: Iterable[Path],
    *,
    group_by: str = "target-environment",
    environment_fields: Iterable[str] | None = None,
    target_filters: Iterable[str] | None = None,
    environment_filters: dict[str, str] | None = None,
) -> str:
    return (
        json.dumps(
            build_matrix_payload(
                run_dirs,
                group_by=group_by,
                environment_fields=environment_fields,
                target_filters=target_filters,
                environment_filters=environment_filters,
            ),
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )


def render_matrix_markdown_report(
    run_dirs: Iterable[Path],
    *,
    group_by: str = "target-environment",
    environment_fields: Iterable[str] | None = None,
    target_filters: Iterable[str] | None = None,
    environment_filters: dict[str, str] | None = None,
) -> str:
    payload = build_matrix_payload(
        run_dirs,
        group_by=group_by,
        environment_fields=environment_fields,
        target_filters=target_filters,
        environment_filters=environment_filters,
    )
    lines = [
        "# FileGate Compatibility Matrix",
        "",
        "## Configuration",
        "",
        f"- **Input runs:** `{payload['input_run_count']}`",
        f"- **Groups:** `{payload['group_count']}`",
        f"- **Cases:** `{payload['total_cases']}`",
        f"- **Group by:** `{payload['group_by']}`",
        f"- **Environment fields:** `{', '.join(payload['environment_fields'])}`",
        f"- **Generated at:** `{payload['generated_at']}`",
    ]

    filters = payload.get("filters_applied") or {}
    target_filters_rendered = ", ".join(filters.get("targets") or []) or "—"
    environment_filters_rendered = _format_environment_filters(filters.get("environment") or {})
    lines.extend(
        [
            f"- **Target filter:** `{target_filters_rendered}`",
            f"- **Environment filter:** `{environment_filters_rendered}`",
            "",
            "## Baseline Policy",
            "",
            "- Phase 4 first iteration uses a **summary-only baseline** instead of a weighted compatibility score.",
            "- A case cell keeps its original status when all observations inside a group agree; otherwise it becomes derived status `mixed`.",
            "- Summary buckets are explicit: `compatible=pass`, `caution=warn`, `problematic=fail/timeout/blocked`, `unavailable=skip/unsupported/manual_required/inconclusive`, plus separate `mixed` and `missing` counts.",
            "",
            "## Group Summary",
            "",
            "| Group | Runs | Observed Cases | Missing Cases | Compatible | Caution | Problematic | Unavailable | Mixed | Consistent | Latest Run |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )

    for group in payload.get("groups", []):
        baseline = group.get("summary_baseline") or {}
        buckets = baseline.get("bucket_counts") or {}
        reproducibility = baseline.get("reproducibility") or {}
        latest_run = group.get("latest_run") or {}
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(group.get("label")),
                    _md_cell(len(group.get("runs") or [])),
                    _md_cell(baseline.get("observed_case_count")),
                    _md_cell(baseline.get("missing_case_count")),
                    _md_cell(buckets.get("compatible")),
                    _md_cell(buckets.get("caution")),
                    _md_cell(buckets.get("problematic")),
                    _md_cell(buckets.get("unavailable")),
                    _md_cell(buckets.get("mixed")),
                    _md_cell(reproducibility.get("consistent_case_count")),
                    _md_cell(latest_run.get("run_id")),
                ]
            )
            + " |"
        )

    lines.extend(["", "## Case Matrix", ""])
    matrix_headers = ["Case ID", "Name", *[str(group.get("label", "unknown-group")) for group in payload.get("groups", [])]]
    lines.append("| " + " | ".join(_md_cell(header) for header in matrix_headers) + " |")
    lines.append("| " + " | ".join(["---", "---", *["---" for _ in payload.get("groups", [])]]) + " |")

    for case in payload.get("cases", []):
        row = [
            _md_cell(case.get("case_id")),
            _md_cell(case.get("case_name")),
        ]
        for cell in case.get("cells", []):
            row.append(_md_cell(_format_markdown_matrix_cell(cell)))
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines) + "\n"


def render_matrix_html_report(
    run_dirs: Iterable[Path],
    *,
    group_by: str = "target-environment",
    environment_fields: Iterable[str] | None = None,
    target_filters: Iterable[str] | None = None,
    environment_filters: dict[str, str] | None = None,
) -> str:
    payload = build_matrix_payload(
        run_dirs,
        group_by=group_by,
        environment_fields=environment_fields,
        target_filters=target_filters,
        environment_filters=environment_filters,
    )
    group_rows = "".join(_render_group_summary_row(group) for group in payload.get("groups", []))
    case_rows = "".join(_render_case_matrix_row(case) for case in payload.get("cases", []))
    group_headers = "".join(
        f"<th>{escape(str(group.get('label', 'unknown-group')))}</th>" for group in payload.get("groups", [])
    )
    filters = payload.get("filters_applied") or {}
    target_filters_rendered = ", ".join(filters.get("targets") or []) or "—"
    environment_filters_rendered = _format_environment_filters(filters.get("environment") or {})

    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>FileGate Compatibility Matrix</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; color: #222; background: #fafafa; }}
    h1, h2 {{ color: #111; }}
    code {{ background: #f0f0f0; padding: 0.1rem 0.3rem; border-radius: 4px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0 2rem; background: white; }}
    th, td {{ border: 1px solid #d0d7de; padding: 0.55rem; text-align: left; vertical-align: top; }}
    th {{ background: #f6f8fa; }}
    .meta-list {{ line-height: 1.8; }}
    .table-scroll {{ overflow-x: auto; }}
    .badge {{ display: inline-block; padding: 0.15rem 0.5rem; border-radius: 999px; font-size: 0.85rem; font-weight: 700; }}
    .status-pass, .status-warn {{ background: #dff3e4; color: #1a7f37; }}
    .status-fail, .status-timeout, .status-blocked, .status-mixed {{ background: #ffebe9; color: #cf222e; }}
    .status-manual_required, .status-inconclusive, .status-skip, .status-unsupported {{ background: #fff8c5; color: #9a6700; }}
    .status-missing {{ background: #eaeef2; color: #57606a; }}
    .cell-meta {{ color: #57606a; font-size: 0.85rem; margin-top: 0.35rem; }}
    ul {{ padding-left: 1.25rem; }}
  </style>
</head>
<body>
  <h1>FileGate Compatibility Matrix</h1>

  <h2>Configuration</h2>
  <div class=\"meta-list\">
    <div><strong>Input runs:</strong> <code>{escape(str(payload.get('input_run_count', 0)))}</code></div>
    <div><strong>Groups:</strong> <code>{escape(str(payload.get('group_count', 0)))}</code></div>
    <div><strong>Cases:</strong> <code>{escape(str(payload.get('total_cases', 0)))}</code></div>
    <div><strong>Group by:</strong> <code>{escape(str(payload.get('group_by', '—')))}</code></div>
    <div><strong>Environment fields:</strong> <code>{escape(', '.join(payload.get('environment_fields', [])) or '—')}</code></div>
    <div><strong>Target filter:</strong> <code>{escape(target_filters_rendered)}</code></div>
    <div><strong>Environment filter:</strong> <code>{escape(environment_filters_rendered)}</code></div>
    <div><strong>Generated at:</strong> <code>{escape(str(payload.get('generated_at', '—')))}</code></div>
  </div>

  <h2>Baseline Policy</h2>
  <ul>
    <li>Phase 4 first iteration uses a <strong>summary-only baseline</strong> instead of a weighted compatibility score.</li>
    <li>A case cell keeps its original status when all observations inside a group agree; otherwise it becomes derived status <code>mixed</code>.</li>
    <li>Summary buckets are explicit: <code>compatible=pass</code>, <code>caution=warn</code>, <code>problematic=fail/timeout/blocked</code>, <code>unavailable=skip/unsupported/manual_required/inconclusive</code>, plus separate <code>mixed</code> and <code>missing</code> counts.</li>
  </ul>

  <h2>Group Summary</h2>
  <table>
    <thead>
      <tr>
        <th>Group</th>
        <th>Runs</th>
        <th>Observed Cases</th>
        <th>Missing Cases</th>
        <th>Compatible</th>
        <th>Caution</th>
        <th>Problematic</th>
        <th>Unavailable</th>
        <th>Mixed</th>
        <th>Consistent</th>
        <th>Latest Run</th>
      </tr>
    </thead>
    <tbody>{group_rows}</tbody>
  </table>

  <h2>Case Matrix</h2>
  <div class=\"table-scroll\">
    <table>
      <thead>
        <tr>
          <th>Case ID</th>
          <th>Name</th>
          {group_headers}
        </tr>
      </thead>
      <tbody>{case_rows}</tbody>
    </table>
  </div>
</body>
</html>
"""


def _prepare_run_report(run_dir: Path) -> dict[str, Any]:
    report = build_report_payload(run_dir)
    generated_at_raw = str(report.get("generated_at") or "")
    projected_run = {
        "run_id": report.get("run_id"),
        "generated_at": generated_at_raw,
        "generated_at_sort": _parse_datetime(generated_at_raw),
        "source_run_directory": str(Path(str(report.get("source_run_directory"))).expanduser().resolve()),
        "target": report.get("target") or {},
        "platform": report.get("platform") or {},
        "counts_by_status": report.get("counts_by_status") or {},
        "warnings": report.get("warnings") or [],
        "case_index": _index_cases(report.get("cases", [])),
    }
    return projected_run


def _normalize_run_dirs(run_dirs: Iterable[Path]) -> list[Path]:
    normalized: dict[str, Path] = {}
    for run_dir in run_dirs:
        resolved = run_dir.expanduser().resolve()
        normalized[str(resolved)] = resolved
    return [normalized[key] for key in sorted(normalized)]


def _normalize_group_by(group_by: str) -> str:
    normalized = group_by.strip().lower()
    if normalized not in MATRIX_GROUP_BY_CHOICES:
        raise ValueError(
            f"Unsupported matrix group_by '{group_by}'. Expected one of: {', '.join(MATRIX_GROUP_BY_CHOICES)}"
        )
    return normalized


def _normalize_environment_fields(environment_fields: Iterable[str] | None) -> tuple[str, ...]:
    if environment_fields is None:
        return MATRIX_ENVIRONMENT_FIELDS
    normalized: list[str] = []
    for field in environment_fields:
        candidate = field.strip()
        if candidate not in MATRIX_ENVIRONMENT_FIELDS:
            raise ValueError(
                f"Unsupported environment field '{field}'. Expected one of: {', '.join(MATRIX_ENVIRONMENT_FIELDS)}"
            )
        if candidate not in normalized:
            normalized.append(candidate)
    return tuple(normalized or MATRIX_ENVIRONMENT_FIELDS)


def _normalize_environment_filters(environment_filters: dict[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for raw_field, raw_value in environment_filters.items():
        field = raw_field.strip()
        if field not in MATRIX_ENVIRONMENT_FIELDS:
            raise ValueError(
                f"Unsupported environment filter field '{raw_field}'. Expected one of: {', '.join(MATRIX_ENVIRONMENT_FIELDS)}"
            )
        value = raw_value.strip().casefold()
        if value:
            normalized[field] = value
    return normalized


def _matches_filters(
    run: dict[str, Any],
    *,
    target_filters: set[str],
    environment_filters: dict[str, str],
) -> bool:
    if target_filters:
        target_name = str((run.get("target") or {}).get("name") or "").strip().casefold()
        if target_name not in target_filters:
            return False

    platform = run.get("platform") or {}
    for field, expected_value in environment_filters.items():
        actual_value = str(platform.get(field) or "").strip().casefold()
        if actual_value != expected_value:
            return False
    return True


def _run_sort_key(run: dict[str, Any]) -> tuple[datetime, str, str]:
    return (
        run.get("generated_at_sort") or datetime.min.replace(tzinfo=UTC),
        str(run.get("run_id") or ""),
        str(run.get("source_run_directory") or ""),
    )


def _parse_datetime(value: str) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=UTC)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=UTC)


def _index_cases(cases: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for case in cases:
        case_id = str((case.get("case") or {}).get("id") or "")
        if case_id:
            indexed[case_id] = case
    return indexed


def _build_case_catalog(runs: list[dict[str, Any]]) -> list[dict[str, str]]:
    ordered: dict[str, dict[str, str]] = {}
    for run in runs:
        for case in (run.get("case_index") or {}).values():
            case_block = case.get("case") or {}
            case_id = str(case_block.get("id") or "")
            if not case_id or case_id in ordered:
                continue
            ordered[case_id] = {
                "case_id": case_id,
                "case_name": str(case_block.get("name") or case_id),
                "automation_level": str(case_block.get("automation_level") or "unknown"),
            }
    return list(ordered.values())


def _build_groups(
    runs: list[dict[str, Any]],
    *,
    group_by: str,
    environment_fields: tuple[str, ...],
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for run in runs:
        signature = _build_group_signature(run, group_by=group_by, environment_fields=environment_fields)
        group = grouped.get(signature["group_id"])
        if group is None:
            group = {
                "group_id": signature["group_id"],
                "label": signature["label"],
                "runs": [],
                "targets": {},
                "environments": {},
            }
            grouped[signature["group_id"]] = group

        group["runs"].append(run)
        target_signature = json.dumps(_target_projection(run.get("target") or {}), sort_keys=True)
        environment_signature = json.dumps(_environment_projection(run.get("platform") or {}), sort_keys=True)
        group["targets"][target_signature] = _target_projection(run.get("target") or {})
        group["environments"][environment_signature] = _environment_projection(run.get("platform") or {})

    normalized_groups: list[dict[str, Any]] = []
    for group in grouped.values():
        group["runs"].sort(key=_run_sort_key)
        normalized_groups.append(
            {
                "group_id": group["group_id"],
                "label": group["label"],
                "runs": group["runs"],
                "targets": sorted(group["targets"].values(), key=lambda item: json.dumps(item, sort_keys=True)),
                "environments": sorted(
                    group["environments"].values(),
                    key=lambda item: json.dumps(item, sort_keys=True),
                ),
            }
        )

    normalized_groups.sort(key=lambda item: (str(item["label"]), str(item["group_id"])))
    return normalized_groups


def _build_group_signature(
    run: dict[str, Any],
    *,
    group_by: str,
    environment_fields: tuple[str, ...],
) -> dict[str, str]:
    target = run.get("target") or {}
    platform = run.get("platform") or {}
    target_name = str(target.get("name") or "unknown-target")
    environment_label = ", ".join(
        f"{field}={str(platform.get(field) or 'unknown')}" for field in environment_fields
    )

    if group_by == "target":
        return {
            "group_id": f"target::{target_name}",
            "label": target_name,
        }
    if group_by == "environment":
        return {
            "group_id": "environment::" + "::".join(str(platform.get(field) or "unknown") for field in environment_fields),
            "label": environment_label,
        }
    return {
        "group_id": (
            f"target-environment::{target_name}::"
            + "::".join(str(platform.get(field) or "unknown") for field in environment_fields)
        ),
        "label": f"{target_name} @ {environment_label}",
    }


def _target_projection(target: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": target.get("name"),
        "version": target.get("version"),
        "sample_app": target.get("sample_app"),
    }


def _environment_projection(platform: dict[str, Any]) -> dict[str, Any]:
    return {field: platform.get(field) for field in MATRIX_ENVIRONMENT_FIELDS}


def _build_group_summary(group: dict[str, Any], all_case_ids: list[str]) -> dict[str, Any]:
    case_cells: list[dict[str, Any]] = []
    aggregated_case_counts = Counter()
    observation_status_counts = Counter()
    bucket_counts = Counter(
        {
            "compatible": 0,
            "caution": 0,
            "problematic": 0,
            "unavailable": 0,
            "mixed": 0,
            "missing": 0,
        }
    )
    consistent_case_count = 0
    mixed_case_count = 0

    for case_id in all_case_ids:
        cell = _build_case_cell(case_id, group)
        if cell is None:
            bucket_counts["missing"] += 1
            continue

        case_cells.append(cell)
        aggregated_status = str(cell.get("aggregated_status") or "mixed")
        aggregated_case_counts[aggregated_status] += 1
        observation_status_counts.update(cell.get("counts_by_status") or {})

        if cell.get("reproducibility") == "consistent":
            consistent_case_count += 1
        else:
            mixed_case_count += 1

        if aggregated_status == "pass":
            bucket_counts["compatible"] += 1
        elif aggregated_status == "warn":
            bucket_counts["caution"] += 1
        elif aggregated_status in MATRIX_PROBLEMATIC_STATUSES:
            bucket_counts["problematic"] += 1
        elif aggregated_status in MATRIX_UNAVAILABLE_STATUSES:
            bucket_counts["unavailable"] += 1
        else:
            bucket_counts["mixed"] += 1

    latest_run = _project_run(group["runs"][-1])
    return {
        "group_id": group["group_id"],
        "label": group["label"],
        "runs": [_project_run(run) for run in group["runs"]],
        "targets": group["targets"],
        "environments": group["environments"],
        "latest_run": latest_run,
        "summary_baseline": {
            "observed_case_count": len(case_cells),
            "missing_case_count": max(0, len(all_case_ids) - len(case_cells)),
            "aggregated_case_counts_by_status": dict(sorted(aggregated_case_counts.items())),
            "observation_counts_by_status": dict(sorted(observation_status_counts.items())),
            "bucket_counts": dict(bucket_counts),
            "reproducibility": {
                "consistent_case_count": consistent_case_count,
                "mixed_case_count": mixed_case_count,
            },
        },
        "case_cells": case_cells,
    }


def _build_case_cell(case_id: str, group: dict[str, Any]) -> dict[str, Any] | None:
    observations: list[dict[str, Any]] = []
    case_name = case_id
    automation_level = "unknown"

    for run in group.get("runs", []):
        case_payload = (run.get("case_index") or {}).get(case_id)
        if case_payload is None:
            continue
        case_block = case_payload.get("case") or {}
        result_block = case_payload.get("result") or {}
        case_name = str(case_block.get("name") or case_name)
        automation_level = str(case_block.get("automation_level") or automation_level)
        observations.append(
            {
                "run_id": run.get("run_id"),
                "generated_at": run.get("generated_at"),
                "generated_at_sort": run.get("generated_at_sort"),
                "source_run_directory": run.get("source_run_directory"),
                "status": str(result_block.get("status") or "inconclusive"),
                "duration_ms": result_block.get("duration_ms"),
                "returned_resource_type": str(result_block.get("returned_resource_type") or "unknown"),
                "error_code": result_block.get("error_code"),
                "notes": result_block.get("notes") or [],
            }
        )

    if not observations:
        return None

    observations.sort(key=lambda item: (
        item.get("generated_at_sort") or datetime.min.replace(tzinfo=UTC),
        str(item.get("run_id") or ""),
        str(item.get("source_run_directory") or ""),
    ))
    latest = observations[-1]
    counts_by_status = Counter(observation["status"] for observation in observations)
    distinct_statuses = sorted(counts_by_status)
    resource_types = sorted({observation["returned_resource_type"] for observation in observations if observation["returned_resource_type"]})
    error_codes = sorted({str(observation["error_code"]) for observation in observations if observation.get("error_code")})
    reproducibility = "consistent" if len(distinct_statuses) == 1 and len(resource_types) <= 1 else "mixed"
    aggregated_status = distinct_statuses[0] if len(distinct_statuses) == 1 else "mixed"

    notes: list[dict[str, str]] = []
    if aggregated_status == "mixed":
        notes.append(
            {
                "code": "mixed_statuses",
                "message": "Observations in this matrix cell do not agree on a single status.",
            }
        )
    if len(resource_types) > 1:
        notes.append(
            {
                "code": "mixed_resource_types",
                "message": "Observations in this matrix cell returned different resource types.",
            }
        )

    return {
        "group_id": group["group_id"],
        "case_id": case_id,
        "case_name": case_name,
        "automation_level": automation_level,
        "observation_count": len(observations),
        "run_ids": [str(observation.get("run_id") or "") for observation in observations],
        "aggregated_status": aggregated_status,
        "latest_status": latest["status"],
        "counts_by_status": dict(sorted(counts_by_status.items())),
        "resource_types": resource_types,
        "error_codes": error_codes,
        "reproducibility": reproducibility,
        "notes": notes,
        "latest_observation": {
            "run_id": latest.get("run_id"),
            "generated_at": latest.get("generated_at"),
            "source_run_directory": latest.get("source_run_directory"),
            "status": latest.get("status"),
            "duration_ms": latest.get("duration_ms"),
            "returned_resource_type": latest.get("returned_resource_type"),
            "error_code": latest.get("error_code"),
            "notes": latest.get("notes") or [],
        },
    }


def _project_run(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": run.get("run_id"),
        "generated_at": run.get("generated_at"),
        "source_run_directory": run.get("source_run_directory"),
        "target": _target_projection(run.get("target") or {}),
        "platform": _environment_projection(run.get("platform") or {}),
        "counts_by_status": dict(sorted((run.get("counts_by_status") or {}).items())),
        "warning_count": len(run.get("warnings") or []),
    }


def _baseline_policy_payload() -> dict[str, Any]:
    return {
        "mode": "summary-only",
        "description": (
            "Phase 4 first iteration publishes a deterministic summary baseline instead of a weighted "
            "compatibility score."
        ),
        "aggregated_status_rule": (
            "A case keeps its original status within a matrix group only when every observation in that "
            "group agrees; otherwise the derived status is 'mixed'."
        ),
        "bucket_rules": {
            "compatible": ["pass"],
            "caution": ["warn"],
            "problematic": sorted(MATRIX_PROBLEMATIC_STATUSES),
            "unavailable": sorted(MATRIX_UNAVAILABLE_STATUSES),
            "mixed": ["mixed"],
            "missing": ["missing"],
        },
        "limitations": [
            "This baseline does not attempt weighted or target-specific conformance scoring.",
            "Repeated runs are preserved as observations and summarized for reproducibility rather than collapsed into a numeric score.",
            "Future framework and platform work should continue emitting normalized per-case results so the matrix can aggregate them without schema changes.",
        ],
    }


def _format_environment_filters(environment_filters: dict[str, str]) -> str:
    if not environment_filters:
        return "—"
    return ", ".join(f"{field}={value}" for field, value in sorted(environment_filters.items()))


def _format_markdown_matrix_cell(cell: dict[str, Any] | None) -> str:
    if cell is None:
        return "—"
    aggregated_status = str(cell.get("aggregated_status") or "mixed")
    observation_count = int(cell.get("observation_count") or 0)
    resource_types = ",".join(cell.get("resource_types") or []) or "unknown"
    if aggregated_status == "mixed":
        status_counts = ", ".join(
            f"{status}×{count}" for status, count in (cell.get("counts_by_status") or {}).items()
        )
        latest_status = str(cell.get("latest_status") or "unknown")
        return f"mixed ({status_counts}; latest={latest_status})"
    if observation_count > 1:
        return f"{aggregated_status} ({resource_types}; runs={observation_count})"
    return f"{aggregated_status} ({resource_types})"


def _md_cell(value: Any) -> str:
    if value is None or value == "":
        return "—"
    return str(value).replace("|", "\\|").replace("\n", " ")


def _render_group_summary_row(group: dict[str, Any]) -> str:
    baseline = group.get("summary_baseline") or {}
    buckets = baseline.get("bucket_counts") or {}
    reproducibility = baseline.get("reproducibility") or {}
    latest_run = group.get("latest_run") or {}
    return (
        "<tr>"
        f"<td>{escape(str(group.get('label', '—')))}</td>"
        f"<td>{escape(str(len(group.get('runs') or [])))}</td>"
        f"<td>{escape(str(baseline.get('observed_case_count', 0)))}</td>"
        f"<td>{escape(str(baseline.get('missing_case_count', 0)))}</td>"
        f"<td>{escape(str(buckets.get('compatible', 0)))}</td>"
        f"<td>{escape(str(buckets.get('caution', 0)))}</td>"
        f"<td>{escape(str(buckets.get('problematic', 0)))}</td>"
        f"<td>{escape(str(buckets.get('unavailable', 0)))}</td>"
        f"<td>{escape(str(buckets.get('mixed', 0)))}</td>"
        f"<td>{escape(str(reproducibility.get('consistent_case_count', 0)))}</td>"
        f"<td><code>{escape(str(latest_run.get('run_id') or '—'))}</code></td>"
        "</tr>"
    )


def _render_case_matrix_row(case: dict[str, Any]) -> str:
    rendered_cells = "".join(f"<td>{_render_html_matrix_cell(cell)}</td>" for cell in case.get("cells", []))
    return (
        "<tr>"
        f"<td><code>{escape(str(case.get('case_id', '—')))}</code></td>"
        f"<td>{escape(str(case.get('case_name', '—')))}</td>"
        f"{rendered_cells}"
        "</tr>"
    )


def _render_html_matrix_cell(cell: dict[str, Any] | None) -> str:
    if cell is None:
        return "<span class=\"badge status-missing\">missing</span>"
    aggregated_status = str(cell.get("aggregated_status") or "mixed")
    badge_class = f"badge status-{escape(aggregated_status)}"
    if aggregated_status == "mixed":
        status_counts = ", ".join(
            f"{escape(str(status))}×{escape(str(count))}" for status, count in (cell.get("counts_by_status") or {}).items()
        )
        latest_status = escape(str(cell.get("latest_status") or "unknown"))
        return (
            f"<span class=\"{badge_class}\">mixed</span>"
            f"<div class=\"cell-meta\">{status_counts}; latest={latest_status}</div>"
        )
    resource_types = ", ".join(escape(str(value)) for value in (cell.get("resource_types") or ["unknown"]))
    observation_count = int(cell.get("observation_count") or 0)
    return (
        f"<span class=\"{badge_class}\">{escape(aggregated_status)}</span>"
        f"<div class=\"cell-meta\">{resource_types}; runs={escape(str(observation_count))}</div>"
    )