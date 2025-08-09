"""Check system dependencies and configuration."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table
from rich.text import Text

from cocode.github import get_auth_status
from cocode.agents.discovery import discover_agents
from cocode.utils.dependencies import DependencyInfo, check_all
from cocode.utils.exit_codes import ExitCode

console = Console()


def _render_table(results: list[DependencyInfo]) -> Table:
    table = Table(title="cocode doctor")
    table.add_column("Dependency", style="bold")
    table.add_column("Installed")
    table.add_column("Version")
    table.add_column("Path", overflow="fold")

    for info in results:
        installed = Text("Yes", style="green") if info.installed else Text("No", style="red")
        table.add_row(info.name, installed, info.version or "-", info.path or "-")
    return table


def doctor_command() -> None:
    """Check system dependencies and configuration."""
    results = check_all()

    # Required tools for CLI use
    required_missing = [r.name for r in results if r.name in {"git", "gh"} and not r.installed]

    # Warn on Python < 3.10 but do not fail the command
    import sys

    py = next((r for r in results if r.name == "python"), None)
    py_warn = sys.version_info < (3, 10)

    console.print(_render_table(results))

    # Show available agents discovered on PATH
    agents = discover_agents()
    agent_table = Table(title="available agents")
    agent_table.add_column("Agent", style="bold")
    agent_table.add_column("Installed")
    agent_table.add_column("Path", overflow="fold")
    for info in agents:
        installed = Text("Yes", style="green") if info.installed else Text("No", style="red")
        agent_table.add_row(info.name, installed, info.path or "-")
    console.print(agent_table)

    # Show GitHub authentication status
    auth = get_auth_status()
    if auth.authenticated:
        if auth.host and auth.username and auth.auth_method:
            console.print(
                f"[green]GitHub:[/green] Logged in to [bold]{auth.host}[/bold] as "
                f"[bold]{auth.username}[/bold] ({auth.auth_method})"
            )
        else:
            console.print("[green]GitHub:[/green] Authenticated (details unavailable)")
    else:
        detail = f" ({auth.error})" if auth.error else ""
        console.print(f"[red]GitHub:[/red] Not authenticated{detail}")

    if py_warn:
        console.print(
            "[yellow]Warning:[/yellow] Python 3.10+ is recommended. Detected "
            f"[bold]{py.version}[/bold] at {py.path}"
        )

    if required_missing:
        console.print("[red]Missing required dependencies:[/red] " + ", ".join(required_missing))
        raise typer.Exit(ExitCode.MISSING_DEPS)

    console.print("[green]All required dependencies are installed.[/green]")
    raise typer.Exit(ExitCode.SUCCESS)
