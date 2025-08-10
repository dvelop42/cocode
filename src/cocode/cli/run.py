"""Run cocode agents on a GitHub issue."""

from collections.abc import Callable
from pathlib import Path

import typer
from rich.console import Console
from typer import Context

from cocode.agents.base import AgentStatus
from cocode.agents.discovery import discover_agents
from cocode.agents.factory import AgentFactory, AgentFactoryError
from cocode.agents.lifecycle import AgentLifecycleManager
from cocode.git.worktree import WorktreeManager
from cocode.github.issues import IssueManager
from cocode.tui.app import CocodeApp
from cocode.utils.exit_codes import ExitCode

console = Console()


def run_command(
    issue: int = typer.Argument(..., help="GitHub issue number"),
    agents: list[str] = typer.Option(None, "--agent", "-a", help="Agents to run"),
    no_tui: bool = typer.Option(False, "--no-tui", help="Run without TUI interface"),
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

        # Discover and create agents
        discovered_agents = discover_agents()
        available_agents = {}

        for agent_info in discovered_agents:
            if agent_info.installed:
                try:
                    # Create agent instance using the factory with dependency validation
                    agent = factory.create_agent(agent_info.name, validate_dependencies=True)
                    available_agents[agent_info.name] = agent
                except AgentFactoryError as e:
                    console.print(
                        f"[yellow]Warning: Could not initialize {agent_info.name}: {e}[/yellow]"
                    )
                    if debug:
                        console.print(f"[dim]{e}[/dim]")

        if not available_agents:
            console.print("[red]No agents found. Run 'cocode init' to configure agents.[/red]")
            console.print("[yellow]Run 'cocode doctor' to check agent dependencies.[/yellow]")
            raise typer.Exit(ExitCode.GENERAL_ERROR)

        # Filter agents if specified
        if agents:
            selected_agents = {
                name: agent for name, agent in available_agents.items() if name in agents
            }
            if not selected_agents:
                console.print(f"[red]None of the specified agents found: {', '.join(agents)}[/red]")
                raise typer.Exit(ExitCode.GENERAL_ERROR)
        else:
            selected_agents = available_agents

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

                def make_stdout_callback(name: str) -> Callable:
                    def callback(line: str) -> None:
                        console.print(f"[dim]{name}:[/dim] {line}")

                    return callback

                def make_stderr_callback(name: str) -> Callable:
                    def callback(line: str) -> None:
                        console.print(f"[dim]{name}:[/dim] [red]{line}[/red]")

                    return callback

                def make_completion_callback(name: str) -> Callable:
                    def callback(status: AgentStatus) -> None:
                        if status.ready:
                            console.print(f"[green]{name}: Agent ready![/green]")
                        elif status.exit_code == 0:
                            console.print(f"[green]{name}: Completed successfully[/green]")
                        else:
                            console.print(f"[red]{name}: Failed - {status.error_message}[/red]")

                    return callback

                on_stdout = make_stdout_callback(agent_name)
                on_stderr = make_stderr_callback(agent_name)
                on_completion = make_completion_callback(agent_name)
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
        if "lifecycle_mgr" in locals():
            lifecycle_mgr.shutdown_all()
        raise typer.Exit(ExitCode.INTERRUPTED) from None
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        if debug:
            import traceback

            traceback.print_exc()
        raise typer.Exit(ExitCode.GENERAL_ERROR) from e
