"""Check system dependencies and configuration."""

import typer
from rich.console import Console

console = Console()


def doctor_command() -> None:
    """Check system dependencies and configuration."""
    console.print("[yellow]Doctor command not yet implemented[/yellow]")
    raise typer.Exit(1)