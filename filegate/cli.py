"""Command-line interface for FileGate."""

from __future__ import annotations

import json
from pathlib import Path

import click

from filegate import __version__
from filegate.cases import DEFAULT_CASE_REGISTRY
from filegate.environment import detect_environment
from filegate.reporting import (
    render_comparison_html_report,
    render_comparison_json_report,
    render_comparison_markdown_report,
    render_html_report,
    render_json_report,
    render_markdown_report,
)
from filegate.runner import RunRequest, Runner, build_target_from_command
from filegate.targets import build_electron_target


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.version_option(version=__version__)
def main() -> None:
    """FileGate CLI for diagnostics, case discovery, execution, and reporting."""


@main.command()
def doctor() -> None:
    """Inspect the local environment required to run FileGate."""
    report = detect_environment()
    click.echo(json.dumps(report.to_dict(), indent=2, sort_keys=True))


@main.command(name="list-cases")
def list_cases() -> None:
    """List available FileGate test cases."""
    for case in DEFAULT_CASE_REGISTRY.all():
        click.echo(f"{case.case_id}\t{case.automation_level}\t{case.name}")


@main.command()
@click.option("--target-name", required=True, help="Logical target name.")
@click.option("--target-command", required=True, help="Command used to launch the target.")
@click.option("--sample-app", required=True, help="Sample app identifier for result payloads.")
@click.option(
    "--case-id",
    "case_ids",
    multiple=True,
    help="Case identifier to execute. May be passed multiple times.",
)
@click.option(
    "--output-dir",
    default="runs",
    show_default=True,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
)
@click.option("--timeout-seconds", type=float, default=None)
@click.option(
    "--working-directory",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    default=None,
)
def run(
    *,
    target_name: str,
    target_command: str,
    sample_app: str,
    case_ids: tuple[str, ...],
    output_dir: Path,
    timeout_seconds: float | None,
    working_directory: Path | None,
) -> None:
    """Execute a FileGate run against a target."""
    target = build_target_from_command(
        name=target_name,
        command=target_command,
        sample_app=sample_app,
        working_directory=str(working_directory) if working_directory else None,
    )
    summary = Runner().run(
        RunRequest(
            target=target,
            output_dir=output_dir,
            case_ids=list(case_ids) or None,
            timeout_seconds=timeout_seconds,
        )
    )
    click.echo(f"Run completed: {summary.run_id}")
    click.echo(f"Summary: {summary.summary_path}")
    for record in summary.case_records:
        click.echo(
            f"- {record.case_id}: {record.status} ({record.duration_ms} ms) -> {record.result_path}"
        )


@main.command(name="run-electron")
@click.option(
    "--case-id",
    "case_ids",
    multiple=True,
    help="Case identifier to execute. May be passed multiple times.",
)
@click.option(
    "--output-dir",
    default="runs",
    show_default=True,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
)
@click.option("--timeout-seconds", type=float, default=None)
def run_electron(case_ids: tuple[str, ...], output_dir: Path, timeout_seconds: float | None) -> None:
    """Execute a FileGate run against the bundled Electron sample target."""
    target = build_electron_target()
    summary = Runner().run(
        RunRequest(
            target=target,
            output_dir=output_dir,
            case_ids=list(case_ids) or None,
            timeout_seconds=timeout_seconds,
        )
    )
    click.echo(f"Run completed: {summary.run_id}")
    click.echo(f"Summary: {summary.summary_path}")
    for record in summary.case_records:
        click.echo(
            f"- {record.case_id}: {record.status} ({record.duration_ms} ms) -> {record.result_path}"
        )


@main.command()
@click.option(
    "--run-dir",
    required=True,
    type=click.Path(exists=True, path_type=Path, file_okay=False, dir_okay=True),
    help="Path to a FileGate run directory containing run-summary.json.",
)
@click.option(
    "--format",
    "report_format",
    required=True,
    type=click.Choice(["json", "markdown", "html"], case_sensitive=False),
    help="Report output format.",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, dir_okay=False),
    default=None,
    help="Optional output file path. Defaults to stdout when omitted.",
)
def report(run_dir: Path, report_format: str, output: Path | None) -> None:
    """Generate reports from a FileGate run result."""
    normalized_format = report_format.lower()
    if normalized_format == "json":
        content = render_json_report(run_dir)
    elif normalized_format == "markdown":
        content = render_markdown_report(run_dir)
    else:
        content = render_html_report(run_dir)

    if output is None:
        click.echo(content, nl=False)
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    click.echo(f"Report written: {output}")


@main.command(name="compare-runs")
@click.option(
    "--left-run-dir",
    required=True,
    type=click.Path(exists=True, path_type=Path, file_okay=False, dir_okay=True),
    help="Path to the left FileGate run directory containing run-summary.json.",
)
@click.option(
    "--right-run-dir",
    required=True,
    type=click.Path(exists=True, path_type=Path, file_okay=False, dir_okay=True),
    help="Path to the right FileGate run directory containing run-summary.json.",
)
@click.option(
    "--format",
    "report_format",
    required=True,
    type=click.Choice(["json", "markdown", "html"], case_sensitive=False),
    help="Comparison report output format.",
)
@click.option(
    "--output",
    type=click.Path(path_type=Path, dir_okay=False),
    default=None,
    help="Optional output file path. Defaults to stdout when omitted.",
)
def compare_runs(
    left_run_dir: Path,
    right_run_dir: Path,
    report_format: str,
    output: Path | None,
) -> None:
    """Generate a side-by-side comparison report for two FileGate runs."""
    normalized_format = report_format.lower()
    if normalized_format == "json":
        content = render_comparison_json_report(left_run_dir, right_run_dir)
    elif normalized_format == "markdown":
        content = render_comparison_markdown_report(left_run_dir, right_run_dir)
    else:
        content = render_comparison_html_report(left_run_dir, right_run_dir)

    if output is None:
        click.echo(content, nl=False)
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    click.echo(f"Comparison report written: {output}")


if __name__ == "__main__":
    main()
