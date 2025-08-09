"""Check system dependencies and configuration."""

from rich.console import Console
import typer

from cocode.utils.exit_codes import ExitCode

console = Console()


def doctor_command() -> None:
    """Check system dependencies and configuration."""
    console.print("[yellow]Doctor command not yet implemented[/yellow]")
    raise typer.Exit(ExitCode.MISSING_DEPS)  # More appropriate for doctor command
