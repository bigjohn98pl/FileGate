"""Markdown renderer for FileGate reports."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from filegate.reporting.json import build_report_payload


def render_markdown_report(run_dir: Path) -> str:
    """Render a FileGate run report as Markdown."""
    report = build_report_payload(run_dir)
    target = report.get("target") or {}
    platform = report.get("platform") or {}
    lines: list[str] = [
        f"# FileGate Report: `{report.get('run_id', 'unknown-run')}`",
        "",
        "## Metadata",
        "",
        f"- **Source run directory:** `{report.get('source_run_directory')}`",
        f"- **Generated at:** `{report.get('generated_at') or '—'}`",
        f"- **Target:** `{target.get('name', '—')}` `{target.get('version', '—')}`",
        f"- **Sample app:** `{target.get('sample_app', '—')}`",
        (
            "- **Platform:** "
            f"`{platform.get('os', '—')}` / `{platform.get('distribution', '—')}` / "
            f"`{platform.get('version', '—')}` / `{platform.get('desktop_environment', '—')}` / "
            f"`{platform.get('session_type', '—')}` / `{platform.get('sandbox', '—')}`"
        ),
        f"- **Total cases:** `{report.get('total_cases', 0)}`",
        "",
        "## Status Summary",
        "",
        "| Status | Count |",
        "| --- | ---: |",
    ]

    for status, count in (report.get("counts_by_status") or {}).items():
        lines.append(f"| `{status}` | {count} |")

    warnings = report.get("warnings") or []
    if warnings:
        lines.extend(["", "## Warnings", ""])
        for warning in warnings:
            lines.append(f"- **{warning.get('code', 'warning')}**: {warning.get('message', '')}")

    lines.extend(
        [
            "",
            "## Cases",
            "",
            "| Case ID | Name | Status | Duration (ms) | Resource Type | Read | Write | Error Code | Notes |",
            "| --- | --- | --- | ---: | --- | --- | --- | --- | --- |",
        ]
    )

    for case in report.get("cases", []):
        case_block = case.get("case") or {}
        result = case.get("result") or {}
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(case_block.get("id")),
                    _md_cell(case_block.get("name")),
                    _md_cell(result.get("status")),
                    _md_cell(result.get("duration_ms")),
                    _md_cell(result.get("returned_resource_type")),
                    _md_cell(_format_bool(result.get("can_read"))),
                    _md_cell(_format_bool(result.get("can_write"))),
                    _md_cell(result.get("error_code")),
                    _md_cell(_format_notes(result.get("notes", []))),
                ]
            )
            + " |"
        )

    return "\n".join(lines) + "\n"


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


def _format_bool(value: Any) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return "—"