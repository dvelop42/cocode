"""Initialize cocode in a repository."""

import typer
from rich.console import Console

console = Console()


def init_command(
    interactive: bool = typer.Option(True, "--interactive/--no-interactive", help="Interactive mode")
) -> None:
    """Initialize cocode configuration in the current repository."""
    console.print("[yellow]Init command not yet implemented[/yellow]")
    raise typer.Exit(1)