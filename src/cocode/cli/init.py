"""Initialize cocode in a repository."""

import logging
import shlex
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from typer import Context

from cocode.agents.discovery import discover_agents
from cocode.config.manager import ConfigManager, ConfigurationError
from cocode.utils.exit_codes import ExitCode

console = Console()
logger = logging.getLogger(__name__)


def init_command(
    interactive: bool = typer.Option(
        True, "--interactive/--no-interactive", help="Interactive mode"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force overwrite existing configuration"
    ),
    ctx: Context = typer.Context,
) -> None:
    """Initialize cocode configuration in the current repository."""
    # Check for dry run mode
    dry_run = ctx.obj.get("dry_run", False) if ctx.obj else False

    if dry_run:
        console.print("\n[bold yellow]🔍 DRY RUN MODE - No changes will be made[/bold yellow]\n")

    config_path = Path(".cocode/config.json")

    # Check if config already exists
    if config_path.exists() and not force:
        console.print("[yellow]Configuration already exists at .cocode/config.json[/yellow]")
        if interactive:
            overwrite = Confirm.ask("Do you want to overwrite it?", default=False)
            if not overwrite:
                console.print("[green]Keeping existing configuration[/green]")
                sys.exit(ExitCode.SUCCESS)
        else:
            console.print("[red]Use --force to overwrite existing configuration[/red]")
            raise typer.Exit(ExitCode.GENERAL_ERROR)

    # Initialize config manager
    config_manager = ConfigManager(config_path)

    # Discover available agents
    discovered_agents = discover_agents()
    available_agents = [agent for agent in discovered_agents if agent.installed]

    # Display discovered agents
    console.print("\n[bold]Discovering available agents...[/bold]\n")

    table = Table(title="Agent Discovery Results")
    table.add_column("Agent", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Path")
    table.add_column("Commands")

    for agent in discovered_agents:
        status = "[green]✓ Installed[/green]" if agent.installed else "[red]✗ Not found[/red]"
        path = agent.path or "-"
        commands = ", ".join(agent.aliases) if agent.aliases else "-"
        table.add_row(agent.name, status, path, commands)

    console.print(table)

    if not available_agents:
        console.print("\n[yellow]No agents found on PATH.[/yellow]")
        console.print("Install one of the following agents to continue:")
        console.print("  • claude-code: Install Claude Code CLI")
        console.print("  • codex-cli: Install Codex CLI")
        raise typer.Exit(ExitCode.MISSING_DEPS)

    # Agent selection
    selected_agents = []

    if interactive:
        console.print("\n[bold]Select agents to configure:[/bold]")
        console.print("(You can select multiple agents for parallel execution)\n")

        for agent in available_agents:
            use_agent = Confirm.ask(f"Configure [cyan]{agent.name}[/cyan]?", default=True)
            if use_agent:
                # Get default command for this agent
                default_command = agent.aliases[0] if agent.aliases else agent.name

                # Allow customizing the command
                custom_command = Prompt.ask(
                    f"Command for [cyan]{agent.name}[/cyan]", default=default_command
                )

                agent_config = {
                    "name": agent.name,
                    "command": custom_command,
                    "args": [],
                }

                # Ask if user wants to add custom arguments
                add_args = Confirm.ask(
                    f"Add custom arguments for [cyan]{agent.name}[/cyan]?", default=False
                )

                if add_args:
                    args_str = Prompt.ask("Arguments (space-separated)", default="")
                    if args_str:
                        # Use shlex.split to properly handle quoted arguments
                        try:
                            agent_config["args"] = shlex.split(args_str)
                        except ValueError as e:
                            console.print(f"[yellow]Warning: Invalid argument format: {e}[/yellow]")
                            agent_config["args"] = []

                selected_agents.append(agent_config)
    else:
        # Non-interactive mode: configure all available agents with defaults
        for agent in available_agents:
            default_command = agent.aliases[0] if agent.aliases else agent.name
            agent_config = {
                "name": agent.name,
                "command": default_command,
                "args": [],
            }
            selected_agents.append(agent_config)

        console.print(
            f"\n[green]Configuring {len(selected_agents)} available agent(s) with defaults[/green]"
        )

    if not selected_agents:
        console.print("\n[yellow]No agents selected. Configuration not created.[/yellow]")
        raise typer.Exit(ExitCode.GENERAL_ERROR)

    # Base agent selection
    base_agent = None

    if len(selected_agents) > 1:
        if interactive:
            console.print("\n[bold]Select base agent for comparisons:[/bold]")
            console.print("(The base agent's solution will be used as reference)\n")

            agent_names = [agent["name"] for agent in selected_agents]
            for i, name in enumerate(agent_names, 1):
                console.print(f"  {i}. {name}")

            choice = Prompt.ask(
                "Choose base agent",
                choices=[str(i) for i in range(1, len(agent_names) + 1)],
                default="1",
            )
            base_agent = agent_names[int(choice) - 1]
        else:
            # Use first agent as base in non-interactive mode
            base_agent = selected_agents[0]["name"]
            console.print(f"Using [cyan]{base_agent}[/cyan] as base agent")
    elif len(selected_agents) == 1:
        base_agent = selected_agents[0]["name"]
        console.print(f"\nUsing [cyan]{base_agent}[/cyan] as base agent")

    # Build configuration
    try:
        # Load defaults and add our agents
        config_manager.load()

        # Clear any existing agents
        config_manager.set("agents", selected_agents)

        # Set base agent
        if base_agent:
            config_manager.set("base_agent", base_agent)

        if dry_run:
            # In dry run mode, show what would be saved
            console.print("\n[yellow]Would save configuration:[/yellow]")
            console.print(f"  Config path: {config_path}")
            console.print(f"  Agents: {[agent['name'] for agent in selected_agents]}")
            console.print(f"  Base agent: {base_agent}")
        else:
            # Save configuration
            config_manager.save()

        # Display summary
        console.print("\n" + "=" * 50)
        if dry_run:
            console.print(
                Panel(
                    f"[yellow]DRY RUN[/yellow] - Configuration would be saved to [cyan].cocode/config.json[/cyan]\n\n"
                    f"Configured agents: {', '.join([str(a['name']) for a in selected_agents])}\n"
                    f"Base agent: {base_agent or 'None'}",
                    title="[bold yellow]Dry Run Complete[/bold yellow]",
                    border_style="yellow",
                )
            )
        else:
            console.print(
                Panel(
                    f"[green]✓[/green] Configuration saved to [cyan].cocode/config.json[/cyan]\n\n"
                    f"Configured agents: {', '.join([str(a['name']) for a in selected_agents])}\n"
                    f"Base agent: {base_agent or 'None'}",
                    title="[bold green]Initialization Complete[/bold green]",
                    border_style="green",
                )
            )

        console.print("\n[bold]Next steps:[/bold]")
        console.print("  1. Review the configuration: [cyan]cat .cocode/config.json[/cyan]")
        console.print("  2. Run agents on an issue: [cyan]cocode run --issue 123[/cyan]")
        console.print("  3. Check system status: [cyan]cocode doctor[/cyan]")

        sys.exit(ExitCode.SUCCESS)

    except ConfigurationError as e:
        console.print(f"[red]Failed to save configuration: {e}[/red]")
        raise typer.Exit(ExitCode.GENERAL_ERROR) from e
    except Exception as e:
        logger.error(f"Unexpected error during init: {e}")
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise typer.Exit(ExitCode.GENERAL_ERROR) from e
