"""Command-line interface for FileGate."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import click

from filegate import __version__
from filegate.artifact_validation import ArtifactValidationError
from filegate.bootstrap import prepare_all_targets, prepare_target
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
from filegate.targets import build_preset_target, list_preset_targets

SAMPLE_TARGET_IDS = ("electron", "python-tkinter", "linux-portal")


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.version_option(version=__version__)
def main() -> None:
    """FileGate CLI for diagnostics, case discovery, execution, and reporting."""


@main.command(name="doctor")
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
@click.argument("target", required=False)
@click.option("--target-name", required=False, help="Logical target name (advanced/custom mode).")
@click.option("--target-command", required=False, help="Command used to launch the target (advanced/custom mode).")
@click.option("--sample-app", required=False, help="Sample app identifier for result payloads (advanced/custom mode).")
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
    "--mode",
    "execution_mode",
    type=click.Choice(["auto", "interactive", "simulation"], case_sensitive=False),
    default="auto",
    show_default=True,
    help="Execution mode. 'auto' chooses interactive when GUI is available, otherwise simulation.",
)
@click.option(
    "--working-directory",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    default=None,
)
def run(
    target: str | None,
    *,
    target_name: str | None,
    target_command: str | None,
    sample_app: str | None,
    case_ids: tuple[str, ...],
    output_dir: Path,
    timeout_seconds: float | None,
    execution_mode: str,
    working_directory: Path | None,
) -> None:
    """Execute a FileGate run against a preset target or custom target command."""
    try:
        if target:
            if any(value is not None for value in (target_name, target_command, sample_app, working_directory)):
                raise click.ClickException(
                    "When positional TARGET is provided, do not pass --target-name/--target-command/--sample-app/--working-directory."
                )
            resolved_target = build_preset_target(target)
        else:
            missing = [
                option_name
                for option_name, option_value in (
                    ("--target-name", target_name),
                    ("--target-command", target_command),
                    ("--sample-app", sample_app),
                )
                if not option_value
            ]
            if missing:
                raise click.ClickException(
                    "Custom mode requires all of: --target-name, --target-command, --sample-app. "
                    f"Missing: {', '.join(missing)}"
                )
            resolved_target = build_target_from_command(
                name=str(target_name),
                command=str(target_command),
                sample_app=str(sample_app),
                working_directory=str(working_directory) if working_directory else None,
            )

        summary = Runner().run(
            RunRequest(
                target=resolved_target,
                output_dir=output_dir,
                case_ids=list(case_ids) or None,
                timeout_seconds=timeout_seconds,
                execution_mode=execution_mode.lower(),
            )
        )
    except ArtifactValidationError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Run completed: {summary.run_id}")
    click.echo(f"Summary: {summary.summary_path}")
    for record in summary.case_records:
        click.echo(
            f"- {record.case_id}: {record.status} ({record.duration_ms} ms) -> {record.result_path}"
        )


@main.command(name="list-targets")
def list_targets() -> None:
    """List bundled target presets available for simplified `run TARGET` workflow."""
    for target in list_preset_targets():
        click.echo(f"{target['id']}\t{target['description']}")


@main.command(name="prepare-target")
@click.argument("target")
def prepare_target_command(target: str) -> None:
    """Prepare and validate one bundled sample target environment."""
    try:
        result = prepare_target(target)
    except KeyError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"[{result.target_id}] {result.status}")
    for detail in result.details:
        click.echo(f"- {detail}")

    if result.status != "ready":
        raise click.ClickException(f"Target '{result.target_id}' is not ready.")


@main.command(name="prepare-samples")
def prepare_samples_command() -> None:
    """Prepare and validate all bundled sample target environments."""
    results = prepare_all_targets()
    has_failure = False
    for result in results:
        click.echo(f"[{result.target_id}] {result.status}")
        for detail in result.details:
            click.echo(f"- {detail}")
        if result.status != "ready":
            has_failure = True

    if has_failure:
        raise click.ClickException("One or more sample targets are not ready.")


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
    try:
        normalized_format = report_format.lower()
        if normalized_format == "json":
            content = render_json_report(run_dir)
        elif normalized_format == "markdown":
            content = render_markdown_report(run_dir)
        else:
            content = render_html_report(run_dir)
    except ArtifactValidationError as exc:
        raise click.ClickException(str(exc)) from exc

    if output is None:
        click.echo(content, nl=False)
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    click.echo(f"Report written: {output}")


@main.command(name="compare-runs")
@click.option(
    "--left-run-dir",
    required=False,
    type=click.Path(exists=True, path_type=Path, file_okay=False, dir_okay=True),
    help="Path to the left FileGate run directory containing run-summary.json.",
)
@click.option(
    "--right-run-dir",
    required=False,
    type=click.Path(exists=True, path_type=Path, file_okay=False, dir_okay=True),
    help="Path to the right FileGate run directory containing run-summary.json.",
)
@click.option(
    "--latest-samples",
    is_flag=True,
    default=False,
    help=(
        "Automatically compare the most recent runs for bundled sample targets "
        "'electron' and 'python-tkinter'."
    ),
)
@click.option(
    "--runs-root",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    default="runs",
    show_default=True,
    help="Root directory containing run subdirectories used by --latest-samples.",
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
    left_run_dir: Path | None,
    right_run_dir: Path | None,
    latest_samples: bool,
    runs_root: Path,
    report_format: str,
    output: Path | None,
) -> None:
    """Generate a side-by-side comparison report for two FileGate runs."""
    try:
        if latest_samples:
            if left_run_dir or right_run_dir:
                raise click.ClickException(
                    "Do not pass --left-run-dir/--right-run-dir when using --latest-samples."
                )
            left_run_dir, right_run_dir = _resolve_latest_sample_runs(runs_root)
        else:
            if left_run_dir is None or right_run_dir is None:
                raise click.ClickException(
                    "Either pass both --left-run-dir and --right-run-dir, or use --latest-samples."
                )

        normalized_format = report_format.lower()
        if normalized_format == "json":
            content = render_comparison_json_report(left_run_dir, right_run_dir)
        elif normalized_format == "markdown":
            content = render_comparison_markdown_report(left_run_dir, right_run_dir)
        else:
            content = render_comparison_html_report(left_run_dir, right_run_dir)
    except ArtifactValidationError as exc:
        raise click.ClickException(str(exc)) from exc

    if output is None:
        click.echo(content, nl=False)
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    click.echo(f"Comparison report written: {output}")


def _resolve_latest_sample_runs(runs_root: Path) -> tuple[Path, Path]:
    normalized_runs_root = runs_root.expanduser().resolve()
    if not normalized_runs_root.exists():
        raise click.ClickException(f"Runs root does not exist: {normalized_runs_root}")

    latest_by_target: dict[str, tuple[datetime, Path]] = {}
    for run_dir in normalized_runs_root.iterdir():
        if not run_dir.is_dir():
            continue
        summary_path = run_dir / "run-summary.json"
        if not summary_path.exists():
            continue

        try:
            summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue

        target_name = str((summary_payload.get("target") or {}).get("name") or "").strip().lower()
        if target_name not in SAMPLE_TARGET_IDS:
            continue

        generated_at_raw = str(summary_payload.get("generated_at") or "").strip()
        generated_at = _parse_generated_at(generated_at_raw)
        if generated_at is None:
            continue

        previous = latest_by_target.get(target_name)
        if previous is None or generated_at > previous[0]:
            latest_by_target[target_name] = (generated_at, run_dir)

    missing_targets = [target for target in SAMPLE_TARGET_IDS if target not in latest_by_target]
    if missing_targets:
        raise click.ClickException(
            "Could not find sample runs for: "
            + ", ".join(missing_targets)
            + f" under {normalized_runs_root}"
        )

    return latest_by_target["electron"][1], latest_by_target["python-tkinter"][1]


def _parse_generated_at(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


main.add_command(doctor, name="doc")
main.add_command(list_cases, name="lc")
main.add_command(list_targets, name="lt")
main.add_command(prepare_target_command, name="pt")
main.add_command(prepare_samples_command, name="ps")
main.add_command(run, name="r")
main.add_command(report, name="rep")
main.add_command(compare_runs, name="cr")


if __name__ == "__main__":
    main()
