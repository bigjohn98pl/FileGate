"""Command-line interface for FileGate."""

from __future__ import annotations

import click

from filegate import __version__


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.version_option(version=__version__)
def main() -> None:
    """FileGate CLI for diagnostics, case discovery, execution, and reporting."""


@main.command()
def doctor() -> None:
    """Inspect the local environment required to run FileGate."""
    click.echo("Environment doctor is not implemented yet.")


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
