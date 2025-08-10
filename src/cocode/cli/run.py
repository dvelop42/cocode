"""Run cocode agents on a GitHub issue."""

import typer
from rich.console import Console
from typer import Context

from cocode.utils.exit_codes import ExitCode

console = Console()


def run_command(
    issue: int = typer.Argument(..., help="GitHub issue number"),
    agents: list[str] = typer.Option(None, "--agent", "-a", help="Agents to run"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug output"),
    ctx: Context = typer.Context,
) -> None:
    """Run agents to fix a GitHub issue."""
    # Check for dry run mode
    dry_run = ctx.obj.get("dry_run", False) if ctx.obj else False
    
    if dry_run:
        console.print("\n[bold yellow]🔍 DRY RUN MODE - No changes will be made[/bold yellow]\n")
        console.print(f"[yellow]Would run agents on issue #{issue}[/yellow]")
        if agents:
            console.print(f"[yellow]Selected agents: {', '.join(agents)}[/yellow]")
        console.print("\n[yellow]Operations that would be performed:[/yellow]")
        console.print("  1. Fetch issue details from GitHub")
        console.print("  2. Create worktrees for each agent")
        console.print("  3. Run agents with issue context")
        console.print("  4. Monitor agent progress")
        console.print("  5. Create pull request with selected solution")
    else:
        console.print(f"[yellow]Run command not yet implemented for issue #{issue}[/yellow]")
    raise typer.Exit(ExitCode.GENERAL_ERROR)
