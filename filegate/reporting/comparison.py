"""Comparison reporting for two FileGate runs."""

from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

from filegate.reporting.json import build_report_payload


def build_comparison_payload(left_run_dir: Path, right_run_dir: Path) -> dict[str, Any]:
    """Build a side-by-side comparison payload for two FileGate runs."""
    left_report = build_report_payload(left_run_dir)
    right_report = build_report_payload(right_run_dir)

    left_cases = _index_cases(left_report)
    right_cases = _index_cases(right_report)
    all_case_ids = sorted(set(left_cases) | set(right_cases))

    comparisons: list[dict[str, Any]] = []
    for case_id in all_case_ids:
        left_case = left_cases.get(case_id)
        right_case = right_cases.get(case_id)
        comparison_notes: list[dict[str, str]] = []
        if left_case is None:
            comparison_notes.append(_note("missing_left_case", f"Case '{case_id}' is absent from the left run."))
        if right_case is None:
            comparison_notes.append(_note("missing_right_case", f"Case '{case_id}' is absent from the right run."))

        left_result = (left_case or {}).get("result") or {}
        right_result = (right_case or {}).get("result") or {}
        if left_case and right_case and str(left_result.get("status")) != str(right_result.get("status")):
            comparison_notes.append(
                _note(
                    "status_difference",
                    f"Statuses differ: {left_result.get('status')} vs {right_result.get('status')}.",
                )
            )
        if left_case and right_case and str(left_result.get("returned_resource_type")) != str(right_result.get("returned_resource_type")):
            comparison_notes.append(
                _note(
                    "resource_type_difference",
                    "Returned resource types differ between targets.",
                )
            )
        if left_case and right_case and str(left_result.get("returned_value_example")) != str(right_result.get("returned_value_example")):
            comparison_notes.append(
                _note(
                    "returned_value_difference",
                    "Returned value examples differ between targets; review extension/filter outcomes before treating this as incompatibility.",
                )
            )
        if left_case and right_case and _format_notes(left_result.get("notes", [])) != _format_notes(right_result.get("notes", [])):
            comparison_notes.append(
                _note(
                    "note_difference",
                    "Structured notes differ between targets; this often captures framework-specific filter or save-extension behavior.",
                )
            )

        comparisons.append(
            {
                "case_id": case_id,
                "case_name": _case_name(left_case, right_case),
                "automation_level": _automation_level(left_case, right_case),
                "left": _project_case(left_case),
                "right": _project_case(right_case),
                "notes": comparison_notes,
            }
        )

    return {
        "schema_version": "0.1",
        "report_format": "comparison-json",
        "left": _project_report(left_report),
        "right": _project_report(right_report),
        "cases": comparisons,
    }


def render_comparison_json_report(left_run_dir: Path, right_run_dir: Path) -> str:
    return json.dumps(build_comparison_payload(left_run_dir, right_run_dir), indent=2, ensure_ascii=False) + "\n"


def render_comparison_markdown_report(left_run_dir: Path, right_run_dir: Path) -> str:
    payload = build_comparison_payload(left_run_dir, right_run_dir)
    left = payload["left"]
    right = payload["right"]
    lines = [
        "# FileGate Comparison Report",
        "",
        "## Targets",
        "",
        f"- **Left:** `{left['target']['name']}` `{left['target']['version']}` — `{left['source_run_directory']}`",
        f"- **Right:** `{right['target']['name']}` `{right['target']['version']}` — `{right['source_run_directory']}`",
        "",
        "## Cases",
        "",
        "| Case ID | Name | Left Status | Right Status | Left Duration | Right Duration | Left Error | Right Error | Notes |",
        "| --- | --- | --- | --- | ---: | ---: | --- | --- | --- |",
    ]

    for case in payload["cases"]:
        left_case = case.get("left") or {}
        right_case = case.get("right") or {}
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(case.get("case_id")),
                    _md_cell(case.get("case_name")),
                    _md_cell(left_case.get("status")),
                    _md_cell(right_case.get("status")),
                    _md_cell(left_case.get("duration_ms")),
                    _md_cell(right_case.get("duration_ms")),
                    _md_cell(left_case.get("error_code")),
                    _md_cell(right_case.get("error_code")),
                    _md_cell(_format_notes(case.get("notes", []))),
                ]
            )
            + " |"
        )

    return "\n".join(lines) + "\n"


def render_comparison_html_report(left_run_dir: Path, right_run_dir: Path) -> str:
    payload = build_comparison_payload(left_run_dir, right_run_dir)
    left = payload["left"]
    right = payload["right"]
    rows = "".join(_render_html_case_row(case) for case in payload["cases"])
    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>FileGate Comparison Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; color: #222; background: #fafafa; }}
    table {{ border-collapse: collapse; width: 100%; background: white; }}
    th, td {{ border: 1px solid #d0d7de; padding: 0.55rem; text-align: left; vertical-align: top; }}
    th {{ background: #f6f8fa; }}
    code {{ background: #f0f0f0; padding: 0.1rem 0.3rem; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>FileGate Comparison Report</h1>
  <p><strong>Left:</strong> <code>{escape(str(left['target']['name']))}</code> <code>{escape(str(left['source_run_directory']))}</code></p>
  <p><strong>Right:</strong> <code>{escape(str(right['target']['name']))}</code> <code>{escape(str(right['source_run_directory']))}</code></p>
  <table>
    <thead>
      <tr>
        <th>Case ID</th>
        <th>Name</th>
        <th>Left Status</th>
        <th>Right Status</th>
        <th>Left Duration</th>
        <th>Right Duration</th>
        <th>Left Error</th>
        <th>Right Error</th>
        <th>Notes</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
</body>
</html>
"""


def _index_cases(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for case in report.get("cases", []):
        case_id = str((case.get("case") or {}).get("id") or "")
        if case_id:
            indexed[case_id] = case
    return indexed


def _project_report(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": report.get("run_id"),
        "source_run_directory": report.get("source_run_directory"),
        "target": report.get("target") or {"name": "unknown", "version": "unknown"},
        "platform": report.get("platform"),
        "counts_by_status": report.get("counts_by_status") or {},
    }


def _project_case(case: dict[str, Any] | None) -> dict[str, Any] | None:
    if case is None:
        return None
    result = case.get("result") or {}
    return {
        "status": result.get("status"),
        "duration_ms": result.get("duration_ms"),
        "returned_resource_type": result.get("returned_resource_type"),
        "returned_value_example": result.get("returned_value_example"),
        "error_code": result.get("error_code"),
        "notes": result.get("notes", []),
    }


def _case_name(left_case: dict[str, Any] | None, right_case: dict[str, Any] | None) -> str:
    for candidate in (left_case, right_case):
        if candidate:
            value = (candidate.get("case") or {}).get("name")
            if value:
                return str(value)
    return "unknown"


def _automation_level(left_case: dict[str, Any] | None, right_case: dict[str, Any] | None) -> str:
    for candidate in (left_case, right_case):
        if candidate:
            value = (candidate.get("case") or {}).get("automation_level")
            if value:
                return str(value)
    return "unknown"


def _note(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _format_notes(notes: list[dict[str, Any]] | Any) -> str:
    if not isinstance(notes, list) or not notes:
        return "—"
    parts: list[str] = []
    for note in notes:
        if isinstance(note, dict):
            code = str(note.get("code", "note"))
            message = str(note.get("message", ""))
            parts.append(f"{code}: {message}" if message else code)
        else:
            parts.append(str(note))
    return "; ".join(parts)


def _md_cell(value: Any) -> str:
    if value is None or value == "":
        return "—"
    return str(value).replace("|", "\\|").replace("\n", " ")


def _render_html_case_row(case: dict[str, Any]) -> str:
    left = case.get("left") or {}
    right = case.get("right") or {}
    return (
        "<tr>"
        f"<td><code>{escape(str(case.get('case_id', '—')))}</code></td>"
        f"<td>{escape(str(case.get('case_name', '—')))}</td>"
        f"<td>{escape(str(left.get('status') or '—'))}</td>"
        f"<td>{escape(str(right.get('status') or '—'))}</td>"
        f"<td>{escape(str(left.get('duration_ms') or '—'))}</td>"
        f"<td>{escape(str(right.get('duration_ms') or '—'))}</td>"
        f"<td><code>{escape(str(left.get('error_code') or '—'))}</code></td>"
        f"<td><code>{escape(str(right.get('error_code') or '—'))}</code></td>"
        f"<td>{escape(_format_notes(case.get('notes', [])))}</td>"
        "</tr>"
    )