"""Show cocode configuration and status."""

import json
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from typer import Context

from cocode.agents.discovery import discover_agents
from cocode.config.manager import ConfigManager
from cocode.git.worktree import WorktreeManager
from cocode.utils.exit_codes import ExitCode

console = Console()


def status_command(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information"),
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
    ctx: Context = typer.Context,
) -> None:
    """Show current cocode configuration and status."""
    # Check for dry run mode
    dry_run = ctx.obj.get("dry_run", False) if ctx.obj else False

    if dry_run:
        console.print("\n[bold yellow]🔍 DRY RUN MODE - Showing status[/bold yellow]\n")

    # Load configuration
    config_path = Path(".cocode/config.json")
    config_exists = config_path.exists()

    status_data: dict[str, Any] = {
        "configuration": {},
        "configured_agents": [],
        "available_agents": [],
        "worktrees": [],
    }

    # Configuration Status
    if config_exists:
        try:
            config_manager = ConfigManager(config_path)
            config_manager.load()

            configured_agents = config_manager.get("agents", [])
            base_agent = config_manager.get("base_agent", None)

            status_data["configuration"] = {
                "path": str(config_path),
                "exists": True,
                "base_agent": base_agent,
                "agent_count": len(configured_agents),
            }
            status_data["configured_agents"] = configured_agents

        except Exception as e:
            status_data["configuration"] = {
                "path": str(config_path),
                "exists": True,
                "error": str(e),
            }
            configured_agents = []
            base_agent = None
    else:
        status_data["configuration"] = {
            "path": str(config_path),
            "exists": False,
        }
        configured_agents = []
        base_agent = None

    # Discover available agents
    discovered_agents = discover_agents()
    status_data["available_agents"] = [
        {
            "name": agent.name,
            "installed": agent.installed,
            "path": agent.path,
            "commands": agent.aliases,
        }
        for agent in discovered_agents
    ]

    # Check for existing worktrees
    repo_root = Path.cwd()
    worktree_mgr = WorktreeManager(repo_root)
    try:
        worktrees = worktree_mgr.list_worktrees()
        status_data["worktrees"] = [
            {
                "path": str(wt),
                "branch": "",  # Branch info not available from list_worktrees
                "agent": (
                    wt.name.replace("cocode_", "") if wt.name.startswith("cocode_") else wt.name
                ),
            }
            for wt in worktrees
        ]
    except Exception:
        status_data["worktrees"] = []

    # Output in JSON format if requested
    if json_output:
        console.print(json.dumps(status_data, indent=2))
        return

    # Display status in rich format
    console.print("\n[bold]Cocode Status[/bold]\n")

    # Configuration Panel
    if config_exists:
        config_content = (
            f"[green]✓[/green] Configuration found at: [cyan]{config_path}[/cyan]\n"
            f"Base agent: [cyan]{base_agent or 'Not set'}[/cyan]\n"
            f"Configured agents: [cyan]{len(configured_agents)}[/cyan]"
        )
        panel_style = "green"
    else:
        config_content = (
            f"[yellow]⚠[/yellow] No configuration found at: [cyan]{config_path}[/cyan]\n"
            f"Run [cyan]cocode init[/cyan] to configure agents"
        )
        panel_style = "yellow"

    console.print(Panel(config_content, title="Configuration", border_style=panel_style))

    # Configured Agents Table
    if configured_agents:
        console.print("\n[bold]Configured Agents[/bold]\n")
        config_table = Table(show_header=True, header_style="bold cyan")
        config_table.add_column("Agent", style="cyan")
        config_table.add_column("Command")
        config_table.add_column("Arguments")
        config_table.add_column("Role")

        for agent in configured_agents:
            role = "[green]Base[/green]" if agent["name"] == base_agent else ""
            args = " ".join(agent.get("args", []))
            config_table.add_row(
                agent["name"],
                agent.get("command", "-"),
                args or "-",
                role,
            )

        console.print(config_table)

    # Available Agents Table
    console.print("\n[bold]Available Agents[/bold]\n")
    avail_table = Table(show_header=True, header_style="bold cyan")
    avail_table.add_column("Agent", style="cyan")
    avail_table.add_column("Status")
    avail_table.add_column("Configured")
    if verbose:
        avail_table.add_column("Path")
        avail_table.add_column("Commands")

    configured_names = {agent["name"] for agent in configured_agents}

    for agent in discovered_agents:
        status = "[green]✓ Installed[/green]" if agent.installed else "[red]✗ Not found[/red]"
        configured = "[green]Yes[/green]" if agent.name in configured_names else "[dim]No[/dim]"

        if verbose:
            path = agent.path or "-"
            commands = ", ".join(agent.aliases) if agent.aliases else "-"
            avail_table.add_row(agent.name, status, configured, path, commands)
        else:
            avail_table.add_row(agent.name, status, configured)

    console.print(avail_table)

    # Worktrees Table (if any exist)
    if status_data["worktrees"]:
        console.print("\n[bold]Active Worktrees[/bold]\n")
        wt_table = Table(show_header=True, header_style="bold cyan")
        wt_table.add_column("Agent", style="cyan")
        wt_table.add_column("Branch")
        if verbose:
            wt_table.add_column("Path")

        for wt in status_data["worktrees"]:
            if verbose:
                wt_table.add_row(wt["agent"], wt["branch"], wt["path"])
            else:
                wt_table.add_row(wt["agent"], wt["branch"])

        console.print(wt_table)

    # Summary and next steps
    console.print("\n[bold]Summary[/bold]\n")

    if config_exists and configured_agents:
        installed_configured = [
            agent["name"]
            for agent in configured_agents
            if any(da.name == agent["name"] and da.installed for da in discovered_agents)
        ]

        if installed_configured:
            console.print(
                f"[green]✓[/green] Ready to run with {len(installed_configured)} agent(s): "
                f"{', '.join(installed_configured)}"
            )
            console.print("\nRun [cyan]cocode run <issue_number>[/cyan] to start agents")
        else:
            console.print(
                "[yellow]⚠[/yellow] Configured agents are not installed. "
                "Run [cyan]cocode doctor[/cyan] to check dependencies"
            )
    else:
        console.print(
            "[yellow]⚠[/yellow] No agents configured. "
            "Run [cyan]cocode init[/cyan] to configure agents"
        )

    if status_data["worktrees"]:
        console.print(
            f"\n[dim]Note: {len(status_data['worktrees'])} worktree(s) found. "
            f"Run [cyan]cocode clean[/cyan] to remove them[/dim]"
        )

    raise typer.Exit(ExitCode.SUCCESS)
