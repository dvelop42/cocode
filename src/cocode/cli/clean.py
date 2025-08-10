"""Clean up cocode artifacts."""

import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table

from cocode.git.sync import SyncStatus
from cocode.git.worktree import WorktreeError, WorktreeManager
from cocode.utils.exit_codes import ExitCode

console = Console()
logger = logging.getLogger(__name__)


def clean_command(
    all: bool = typer.Option(False, "--all", help="Remove all cocode artifacts"),
    sync_first: bool = typer.Option(False, "--sync", help="Sync worktrees before cleaning"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompts"),
    interactive: bool = typer.Option(
        True, "--interactive/--no-interactive", help="Enable interactive mode"
    ),
) -> None:
    """Clean up cocode worktrees and branches.

    This command helps manage cocode worktrees by:
    - Listing all cocode worktrees
    - Optionally syncing them with upstream changes
    - Removing selected or all worktrees
    - Cleaning up associated branches
    """
    try:
        # Get current directory as repo path
        repo_path = Path.cwd()

        # Initialize worktree manager
        try:
            manager = WorktreeManager(repo_path)
        except WorktreeError as e:
            console.print(f"[red]Error:[/red] {e}")
            console.print("[yellow]Make sure you're in a git repository[/yellow]")
            raise typer.Exit(ExitCode.GENERAL_ERROR) from e

        # List existing worktrees
        worktrees = manager.list_worktrees()

        if not worktrees:
            console.print("[green]No cocode worktrees found[/green]")
            raise typer.Exit(ExitCode.SUCCESS)

        # Display worktrees
        table = Table(title="Cocode Worktrees")
        table.add_column("Path", style="cyan")
        table.add_column("Branch", style="yellow")
        table.add_column("Status", style="green")

        worktree_info = {}
        for worktree_path in worktrees:
            try:
                info = manager.get_worktree_info(worktree_path)
                worktree_info[worktree_path] = info

                status = "Modified" if info["has_changes"] else "Clean"
                table.add_row(str(worktree_path.name), info["branch"], status)
            except WorktreeError as e:
                logger.warning(f"Could not get info for {worktree_path}: {e}")
                table.add_row(str(worktree_path.name), "Unknown", "Error")

        console.print(table)

        # Sync worktrees if requested
        if sync_first:
            console.print("\n[cyan]Syncing worktrees with upstream changes...[/cyan]")

            sync_results = manager.sync_all_worktrees()

            # Display sync results
            sync_table = Table(title="Sync Results")
            sync_table.add_column("Worktree", style="cyan")
            sync_table.add_column("Status", style="yellow")
            sync_table.add_column("Details", style="white")

            for worktree_path, result in sync_results.items():
                status_style = "green" if result.status == SyncStatus.CLEAN else "yellow"
                if result.status == SyncStatus.ERROR:
                    status_style = "red"
                elif result.status == SyncStatus.CONFLICTS:
                    status_style = "magenta"

                sync_table.add_row(
                    str(worktree_path.name),
                    f"[{status_style}]{result.status.value}[/{status_style}]",
                    result.message,
                )

                # Show conflicts if any
                if result.conflicts:
                    console.print(f"\n[magenta]Conflicts in {worktree_path.name}:[/magenta]")
                    for conflict_file in result.conflicts:
                        console.print(f"  - {conflict_file}")

            console.print(sync_table)

        # Determine what to clean
        if all:
            to_remove = worktrees
            if interactive and not force:
                if not Confirm.ask(f"Remove all {len(worktrees)} worktrees?"):
                    console.print("[yellow]Operation cancelled[/yellow]")
                    raise typer.Exit(ExitCode.SUCCESS)
        else:
            # Interactive selection
            if not interactive:
                console.print("[yellow]Use --all flag in non-interactive mode[/yellow]")
                raise typer.Exit(ExitCode.GENERAL_ERROR)

            console.print("\n[cyan]Select worktrees to remove:[/cyan]")
            to_remove = []

            for worktree_path in worktrees:
                info = worktree_info.get(worktree_path, {})
                status = "Modified" if info.get("has_changes", False) else "Clean"

                if Confirm.ask(f"Remove {worktree_path.name} ({status})?", default=False):
                    to_remove.append(worktree_path)

            if not to_remove:
                console.print("[yellow]No worktrees selected for removal[/yellow]")
                raise typer.Exit(ExitCode.SUCCESS)

        # Remove selected worktrees
        console.print(f"\n[cyan]Removing {len(to_remove)} worktree(s)...[/cyan]")

        removed_count = 0
        failed_count = 0

        for worktree_path in to_remove:
            try:
                console.print(f"Removing {worktree_path.name}...", end=" ")
                manager.remove_worktree(worktree_path)
                console.print("[green]✓[/green]")
                removed_count += 1
            except WorktreeError as e:
                console.print(f"[red]✗[/red] {e}")
                failed_count += 1

        # Summary
        console.print(f"\n[green]Successfully removed {removed_count} worktree(s)[/green]")
        if failed_count > 0:
            console.print(f"[red]Failed to remove {failed_count} worktree(s)[/red]")
            raise typer.Exit(ExitCode.GENERAL_ERROR)

        raise typer.Exit(ExitCode.SUCCESS)

    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        raise typer.Exit(ExitCode.INTERRUPTED) from None
    except typer.Exit as e:
        # Allow Typer's normal exit flow (e.g., success codes) to pass through
        raise e
    except Exception as e:
        logger.exception("Unexpected error in clean command")
        console.print(f"[red]Unexpected error:[/red] {e}")
        raise typer.Exit(ExitCode.GENERAL_ERROR) from e
