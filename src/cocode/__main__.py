"""Entry point for cocode CLI."""

import sys

import typer
from rich.console import Console

from cocode import __version__
from cocode.cli.clean import clean_command
from cocode.cli.doctor import doctor_command
from cocode.cli.init import init_command
from cocode.cli.run import run_command
from cocode.utils.logging import setup_logging

app = typer.Typer(
    name="cocode",
    help="Orchestrate multiple code agents to fix GitHub issues",
    add_completion=True,
    no_args_is_help=True,
)
console = Console()

# Register commands
app.command("init")(init_command)
app.command("run")(run_command)
app.command("doctor")(doctor_command)
app.command("clean")(clean_command)


@app.callback()
def _global_options(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show the cocode version and exit",
        is_eager=True,
    ),
    log_level: str = typer.Option(
        "INFO",
        "--log-level",
        "-l",
        help="Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
        case_sensitive=False,
    ),
) -> None:
    """Global options processed before subcommands."""
    if version:
        console.print(f"cocode {__version__}")
        raise typer.Exit()
    # Initialize logging as early as possible
    setup_logging(log_level.upper())


def main() -> int:
    """Main entry point for the CLI."""
    try:
        app()
        return 0
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        return 130
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
