"""Run cocode agents on a GitHub issue."""

import json
from collections.abc import Callable
from pathlib import Path

import typer
from rich.console import Console
from rich.prompt import Confirm
from typer import Context

from cocode.agents.base import Agent, AgentStatus
from cocode.agents.discovery import discover_agents
from cocode.agents.factory import AgentFactory, AgentFactoryError
from cocode.agents.lifecycle import AgentLifecycleManager
from cocode.config.manager import ConfigManager
from cocode.git.worktree import WorktreeManager
from cocode.github.issues import IssueManager
from cocode.tui.app import CocodeApp
from cocode.utils.exit_codes import ExitCode

console = Console()


def prompt_and_run_init(ctx: Context, force: bool = False) -> bool:
    """Prompt user to run init and execute if confirmed.

    Args:
        ctx: Typer context
        force: Whether to force overwrite existing configuration

    Returns:
        True if init was run successfully, False otherwise
    """
    from cocode.cli.init import init_command

    console.print("\n[blue]Starting initialization...[/blue]\n")

    try:
        # Run init in interactive mode
        # Pass the context object directly
        init_command(interactive=True, force=force, ctx=ctx)
        return True
    except typer.Exit:
        # init_command raises Exit on success or failure
        # Check if config was actually created
        return Path(".cocode/config.json").exists()


def load_configured_agents(
    config_path: Path, factory: AgentFactory, debug: bool = False
) -> dict[str, Agent]:
    """Load and validate configured agents from configuration file.

    Args:
        config_path: Path to configuration file
        factory: Agent factory instance
        debug: Whether to show debug output

    Returns:
        Dictionary of agent name to Agent instance
    """
    available_agents: dict[str, Agent] = {}

    if not config_path.exists():
        return available_agents

    try:
        config_manager = ConfigManager(config_path)
        config_manager.load()
        configured_agents = config_manager.get("agents", [])

        if configured_agents:
            console.print("[blue]Loading configured agents from .cocode/config.json...[/blue]")
            for agent_config in configured_agents:
                agent_name = agent_config.get("name")
                if agent_name:
                    try:
                        # Create agent instance with configuration from init
                        config_override = {}
                        if agent_config.get("command"):
                            config_override["command"] = agent_config["command"]
                        if agent_config.get("args"):
                            config_override["args"] = agent_config["args"]

                        agent = factory.create_agent(
                            agent_name,
                            config_override=config_override if config_override else None,
                            validate_dependencies=True,
                        )
                        available_agents[agent_name] = agent
                        if debug:
                            console.print(f"[dim]Loaded {agent_name} from config[/dim]")
                    except AgentFactoryError as e:
                        console.print(
                            f"[yellow]Warning: Could not initialize {agent_name}: {e}[/yellow]"
                        )
                        if debug:
                            console.print(f"[dim]{e}[/dim]")
    except (FileNotFoundError, PermissionError) as e:
        console.print(f"[yellow]Warning: Could not access configuration file: {e}[/yellow]")
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        console.print(f"[yellow]Warning: Invalid configuration format: {e}[/yellow]")

    return available_agents


def _print_dry_run(issue: int, agents: list[str] | None) -> None:
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


def _select_agents(available: dict[str, Agent], requested: list[str] | None) -> dict[str, Agent]:
    if not requested:
        return available
    selected = {name: agent for name, agent in available.items() if name in requested}
    return selected


def _make_cli_callbacks(
    name: str,
) -> tuple[Callable[[str], None], Callable[[str], None], Callable[[AgentStatus], None]]:
    def on_stdout(line: str) -> None:
        console.print(f"[dim]{name}:[/dim] {line}")

    def on_stderr(line: str) -> None:
        console.print(f"[dim]{name}:[/dim] [red]{line}[/red]")

    def on_completion(status: AgentStatus) -> None:
        if status.ready:
            console.print(f"[green]{name}: Agent ready![/green]")
        elif status.exit_code == 0:
            console.print(f"[green]{name}: Completed successfully[/green]")
        else:
            console.print(f"[red]{name}: Failed - {status.error_message}[/red]")

    return on_stdout, on_stderr, on_completion


def run_command(
    issue: int = typer.Argument(..., help="GitHub issue number"),
    agents: list[str] | None = typer.Option(None, "--agent", "-a", help="Agents to run"),
    no_tui: bool = typer.Option(False, "--no-tui", help="Run without TUI interface"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug output"),
    ctx: Context = None,
) -> None:
    """Run agents to fix a GitHub issue."""
    # Check for dry run mode
    dry_run = ctx.obj.get("dry_run", False) if ctx.obj else False
    if dry_run:
        _print_dry_run(issue, agents)
        raise typer.Exit(ExitCode.SUCCESS)

    try:
        # Initialize managers
        console.print(f"[blue]Fetching issue #{issue}...[/blue]")
        issue_mgr = IssueManager()
        issue_data = issue_mgr.get_issue(issue)

        if not issue_data:
            console.print(f"[red]Failed to fetch issue #{issue}[/red]")
            raise typer.Exit(ExitCode.GENERAL_ERROR)

        # Initialize agent factory
        factory = AgentFactory()

        # Load configuration to get configured agents
        config_path = Path(".cocode/config.json")

        # Check if configuration exists, if not prompt to run init
        if not config_path.exists():
            console.print("[yellow]⚠ No configuration found.[/yellow]")
            console.print("Cocode needs to be initialized before running agents.")

            # Check if any agents are installed
            discovered = discover_agents()
            installed = [a for a in discovered if a.installed]

            if installed:
                console.print(f"\n[green]Found {len(installed)} installed agent(s):[/green]")
                for agent_info in installed:
                    console.print(f"  • {agent_info.name}")

                # Prompt to run init
                console.print("\nWould you like to initialize cocode now?")
                if Confirm.ask("Run 'cocode init'", default=True):
                    if prompt_and_run_init(ctx, force=False):
                        console.print("\n[green]✓ Configuration created successfully![/green]")
                        console.print(f"\n[blue]Continuing with issue #{issue}...[/blue]\n")
                    else:
                        console.print("\n[red]Configuration was not created. Exiting.[/red]")
                        raise typer.Exit(ExitCode.GENERAL_ERROR)
                else:
                    console.print(
                        "\n[yellow]Please run 'cocode init' to configure agents first.[/yellow]"
                    )
                    raise typer.Exit(ExitCode.GENERAL_ERROR)
            else:
                console.print("\n[red]No agents found on PATH.[/red]")
                console.print("Please install one of the following agents:")
                console.print("  • claude-code: Anthropic's Claude CLI")
                console.print("  • codex-cli: OpenAI Codex CLI")
                console.print("\nThen run 'cocode init' to configure agents.")
                raise typer.Exit(ExitCode.MISSING_DEPS)

        # Try to load configured agents
        available_agents = load_configured_agents(config_path, factory, debug)

        # If no configured agents loaded, offer to re-run init
        if not available_agents:
            console.print("[yellow]⚠ No agents could be loaded from configuration.[/yellow]")

            # Check if configuration might be corrupted or outdated
            if config_path.exists():
                console.print("The configuration file exists but no agents were loaded.")
                console.print("This might happen if:")
                console.print("  • The configured agents are not installed")
                console.print("  • The configuration file is corrupted")

                if Confirm.ask("\nWould you like to reconfigure cocode?", default=True):
                    if prompt_and_run_init(ctx, force=True):
                        # Reload configuration
                        console.print("\n[blue]Reloading configuration...[/blue]")
                        available_agents = load_configured_agents(config_path, factory, debug)

        if not available_agents:
            console.print("\n[red]No agents could be initialized.[/red]")
            console.print("Please check:")
            console.print("  1. Agents are installed: [cyan]cocode doctor[/cyan]")
            console.print("  2. Configuration is valid: [cyan]cocode status[/cyan]")
            console.print("  3. Reconfigure if needed: [cyan]cocode init --force[/cyan]")
            raise typer.Exit(ExitCode.GENERAL_ERROR)

        # Filter agents if specified
        selected_agents = _select_agents(available_agents, agents)
        if agents and not selected_agents:
            console.print(f"[red]None of the specified agents found: {', '.join(agents)}[/red]")
            raise typer.Exit(ExitCode.GENERAL_ERROR)

        console.print(f"[green]Selected agents: {', '.join(selected_agents.keys())}[/green]")

        # Initialize lifecycle manager
        lifecycle_mgr = AgentLifecycleManager()

        # Create worktrees and register agents
        repo_root = Path.cwd()
        worktree_mgr = WorktreeManager(repo_root)

        for agent_name, agent in selected_agents.items():
            console.print(f"[blue]Preparing worktree for {agent_name}...[/blue]")
            branch_name = f"cocode/{issue}-{agent_name}"
            worktree_path = worktree_mgr.create_worktree(
                branch_name=branch_name,
                agent_name=agent_name,
            )
            lifecycle_mgr.register_agent(agent, worktree_path)

        if no_tui:
            # Run without TUI
            console.print("[blue]Starting agents...[/blue]")

            for agent_name in selected_agents:
                on_stdout, on_stderr, on_completion = _make_cli_callbacks(agent_name)
                lifecycle_mgr.start_agent(
                    agent_name,
                    issue,
                    issue_data["body"],
                    issue_data["url"],
                    stdout_callback=on_stdout,
                    stderr_callback=on_stderr,
                    completion_callback=on_completion,
                )

            # Wait for completion
            console.print("[blue]Waiting for agents to complete...[/blue]")
            lifecycle_mgr.wait_for_completion()

            # Show results
            console.print("\n[bold]Results:[/bold]")
            for agent_name in selected_agents:
                info = lifecycle_mgr.get_agent_info(agent_name)
                if info and info.status:
                    if info.status.ready:
                        console.print(f"[green]✓ {agent_name}: Ready[/green]")
                    elif info.status.exit_code == 0:
                        console.print(f"[green]✓ {agent_name}: Completed[/green]")
                    else:
                        console.print(f"[red]✗ {agent_name}: Failed[/red]")

        else:
            # Run with TUI
            app = CocodeApp(
                lifecycle_manager=lifecycle_mgr,
                issue_number=issue,
                issue_body=issue_data["body"],
                issue_url=issue_data["url"],
                dry_run=False,
            )

            # Start agents when TUI launches
            app.call_after_refresh(app.start_all_agents)

            # Run the TUI
            app.run()

        # Cleanup
        lifecycle_mgr.shutdown_all()

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        try:
            lifecycle_mgr.shutdown_all()
        except Exception:
            pass
        raise typer.Exit(ExitCode.INTERRUPTED) from None
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        if debug:
            import traceback

            traceback.print_exc()
        raise typer.Exit(ExitCode.GENERAL_ERROR) from e
