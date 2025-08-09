"""Clean up cocode artifacts."""

import typer
from rich.console import Console

from cocode.utils.exit_codes import ExitCode

console = Console()


def clean_command(
    all: bool = typer.Option(False, "--all", help="Remove all cocode artifacts")
) -> None:
    """Clean up cocode worktrees and branches."""
    console.print("[yellow]Clean command not yet implemented[/yellow]")
    raise typer.Exit(ExitCode.GENERAL_ERROR)
