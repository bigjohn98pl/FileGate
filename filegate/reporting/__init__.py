"""Reporting helpers for FileGate run outputs."""

from filegate.reporting.comparison import (
    build_comparison_payload,
    render_comparison_html_report,
    render_comparison_json_report,
    render_comparison_markdown_report,
)
from filegate.reporting.json import build_report_payload, render_json_report
from filegate.reporting.markdown import render_markdown_report
from filegate.reporting.html import render_html_report
from filegate.reporting.matrix import (
    build_matrix_payload,
    render_matrix_html_report,
    render_matrix_json_report,
    render_matrix_markdown_report,
)

__all__ = [
    "build_comparison_payload",
    "build_matrix_payload",
    "build_report_payload",
    "render_comparison_html_report",
    "render_comparison_json_report",
    "render_comparison_markdown_report",
    "render_json_report",
    "render_matrix_html_report",
    "render_matrix_json_report",
    "render_matrix_markdown_report",
    "render_markdown_report",
    "render_html_report",
]