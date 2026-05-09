"""Command-line interface for FileGate."""

from __future__ import annotations

import json

import click

from filegate import __version__
from filegate.environment import detect_environment


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
    click.echo("Case listing is not implemented yet.")


@main.command()
def run() -> None:
    """Execute a FileGate run against a target."""
    click.echo("Run execution is not implemented yet.")


@main.command()
def report() -> None:
    """Generate reports from a FileGate run result."""
    click.echo("Report generation is not implemented yet.")


if __name__ == "__main__":
    main()
