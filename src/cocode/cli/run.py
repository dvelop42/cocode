"""Run cocode agents on a GitHub issue."""

import typer
from rich.console import Console

from cocode.utils.exit_codes import ExitCode

console = Console()


def run_command(
    issue: int = typer.Argument(..., help="GitHub issue number"),
    agents: list[str] = typer.Option(None, "--agent", "-a", help="Agents to run"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug output"),
) -> None:
    """Run agents to fix a GitHub issue."""
    console.print(f"[yellow]Run command not yet implemented for issue #{issue}[/yellow]")
    raise typer.Exit(ExitCode.GENERAL_ERROR)
