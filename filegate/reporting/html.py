"""Static HTML renderer for FileGate reports."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from filegate.reporting.json import build_report_payload


def render_html_report(run_dir: Path) -> str:
    """Render a FileGate run report as static HTML."""
    report = build_report_payload(run_dir)
    target = report.get("target") or {}
    platform = report.get("platform") or {}
    warning_items = "".join(
        f"<li><strong>{escape(str(w.get('code', 'warning')))}</strong>: {escape(str(w.get('message', '')))}</li>"
        for w in (report.get("warnings") or [])
    )
    status_rows = "".join(
        f"<tr><td><code>{escape(str(status))}</code></td><td>{escape(str(count))}</td></tr>"
        for status, count in (report.get("counts_by_status") or {}).items()
    )
    case_rows = "".join(_render_case_row(case) for case in report.get("cases", []))

    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>FileGate Report {escape(str(report.get('run_id', 'unknown-run')))}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; color: #222; background: #fafafa; }}
    h1, h2 {{ color: #111; }}
    code {{ background: #f0f0f0; padding: 0.1rem 0.3rem; border-radius: 4px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0 2rem; background: white; }}
    th, td {{ border: 1px solid #d0d7de; padding: 0.55rem; text-align: left; vertical-align: top; }}
    th {{ background: #f6f8fa; }}
    .meta-list {{ line-height: 1.7; }}
    .badge {{ display: inline-block; padding: 0.15rem 0.5rem; border-radius: 999px; font-size: 0.9rem; font-weight: 700; }}
    .status-pass, .status-warn {{ background: #dff3e4; color: #1a7f37; }}
    .status-fail, .status-timeout, .status-blocked {{ background: #ffebe9; color: #cf222e; }}
    .status-manual_required, .status-inconclusive, .status-skip, .status-unsupported {{ background: #fff8c5; color: #9a6700; }}
    ul {{ padding-left: 1.25rem; }}
  </style>
</head>
<body>
  <h1>FileGate Report: <code>{escape(str(report.get('run_id', 'unknown-run')))}</code></h1>

  <h2>Metadata</h2>
  <div class=\"meta-list\">
    <div><strong>Source run directory:</strong> <code>{escape(str(report.get('source_run_directory')))}</code></div>
    <div><strong>Generated at:</strong> <code>{escape(str(report.get('generated_at') or '—'))}</code></div>
    <div><strong>Target:</strong> <code>{escape(str(target.get('name', '—')))}</code> <code>{escape(str(target.get('version', '—')))}</code></div>
    <div><strong>Sample app:</strong> <code>{escape(str(target.get('sample_app', '—')))}</code></div>
    <div><strong>Platform:</strong> <code>{escape(str(platform.get('os', '—')))}</code> / <code>{escape(str(platform.get('distribution', '—')))}</code> / <code>{escape(str(platform.get('version', '—')))}</code> / <code>{escape(str(platform.get('desktop_environment', '—')))}</code> / <code>{escape(str(platform.get('session_type', '—')))}</code> / <code>{escape(str(platform.get('sandbox', '—')))}</code></div>
    <div><strong>Total cases:</strong> <code>{escape(str(report.get('total_cases', 0)))}</code></div>
  </div>

  <h2>Status Summary</h2>
  <table>
    <thead><tr><th>Status</th><th>Count</th></tr></thead>
    <tbody>{status_rows}</tbody>
  </table>

  {('<h2>Warnings</h2><ul>' + warning_items + '</ul>') if warning_items else ''}

  <h2>Cases</h2>
  <table>
    <thead>
      <tr>
        <th>Case ID</th>
        <th>Name</th>
        <th>Status</th>
        <th>Duration (ms)</th>
        <th>Resource Type</th>
        <th>Read</th>
        <th>Write</th>
        <th>Error Code</th>
        <th>Notes</th>
      </tr>
    </thead>
    <tbody>{case_rows}</tbody>
  </table>
</body>
</html>
"""


def _render_case_row(case: dict[str, Any]) -> str:
    case_block = case.get("case") or {}
    result = case.get("result") or {}
    status = str(result.get("status") or "inconclusive")
    badge_class = f"badge status-{status}"
    return (
        "<tr>"
        f"<td><code>{escape(str(case_block.get('id', '—')))}</code></td>"
        f"<td>{escape(str(case_block.get('name', '—')))}</td>"
        f"<td><span class=\"{escape(badge_class)}\">{escape(status)}</span></td>"
        f"<td>{escape(str(result.get('duration_ms', '—')))}</td>"
        f"<td><code>{escape(str(result.get('returned_resource_type', '—')))}</code></td>"
        f"<td>{escape(_format_bool(result.get('can_read')))}</td>"
        f"<td>{escape(_format_bool(result.get('can_write')))}</td>"
        f"<td><code>{escape(str(result.get('error_code') or '—'))}</code></td>"
        f"<td>{escape(_format_notes(result.get('notes', [])))}</td>"
        "</tr>"
    )


def _format_notes(notes: list[dict[str, Any]] | Any) -> str:
    if not isinstance(notes, list) or not notes:
        return "—"
    rendered: list[str] = []
    for note in notes:
        if isinstance(note, dict):
            code = str(note.get("code", "note"))
            message = str(note.get("message", ""))
            rendered.append(f"{code}: {message}" if message else code)
        else:
            rendered.append(str(note))
    return "; ".join(rendered)


def _format_bool(value: Any) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return "—"