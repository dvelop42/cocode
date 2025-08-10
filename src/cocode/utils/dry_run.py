"""Dry run utilities for preview and formatting."""

import logging
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

logger = logging.getLogger(__name__)
console = Console()


class DryRunFormatter:
    """Format and display dry run operations."""

    def __init__(self, enabled: bool = False):
        """Initialize the formatter.

        Args:
            enabled: Whether dry run mode is enabled.
        """
        self.enabled = enabled

    def format_operation(self, operation: str, details: str | None = None) -> None:
        """Format and display a dry run operation.

        Args:
            operation: The operation that would be performed.
            details: Optional additional details about the operation.
        """
        if not self.enabled:
            return

        console.print(f"[yellow]Would {operation}[/yellow]")
        if details:
            console.print(f"  [dim]{details}[/dim]")

    def format_command(self, command: list[str] | str) -> None:
        """Format and display a command that would be executed.

        Args:
            command: The command that would be executed.
        """
        if not self.enabled:
            return

        if isinstance(command, list):
            command = " ".join(command)

        console.print(f"[yellow]Would execute:[/yellow] [cyan]{command}[/cyan]")

    def format_file_operation(
        self, operation: str, file_path: str, content: str | None = None
    ) -> None:
        """Format and display a file operation.

        Args:
            operation: The file operation (create, modify, delete, etc.).
            file_path: Path to the file.
            content: Optional content preview.
        """
        if not self.enabled:
            return

        console.print(f"[yellow]Would {operation} file:[/yellow] [cyan]{file_path}[/cyan]")
        if content:
            # Show first few lines of content
            lines = content.split("\n")[:5]
            for line in lines:
                console.print(f"  [dim]{line}[/dim]")
            if len(content.split("\n")) > 5:
                console.print("  [dim]...[/dim]")

    def show_summary(self, operations: list[str]) -> None:
        """Show a summary of operations that would be performed.

        Args:
            operations: List of operation descriptions.
        """
        if not self.enabled or not operations:
            return

        text = Text()
        text.append("DRY RUN SUMMARY\n", style="bold yellow")
        text.append("The following operations would be performed:\n\n", style="yellow")

        for i, op in enumerate(operations, 1):
            text.append(f"  {i}. {op}\n", style="yellow")

        panel = Panel(
            text,
            title="[bold yellow]Dry Run Mode[/bold yellow]",
            border_style="yellow",
            expand=False,
        )
        console.print(panel)

    def log_operation(self, operation: str, details: dict[str, Any] | None = None) -> None:
        """Log a dry run operation for debugging.

        Args:
            operation: The operation being simulated.
            details: Optional operation details.
        """
        if not self.enabled:
            return

        if details:
            logger.info(f"[DRY RUN] {operation}: {details}")
        else:
            logger.info(f"[DRY RUN] {operation}")


def get_dry_run_context(ctx: Any) -> bool:
    """Extract dry run flag from context.

    Args:
        ctx: Typer context object.

    Returns:
        True if dry run mode is enabled.
    """
    if hasattr(ctx, "obj") and ctx.obj:
        return bool(ctx.obj.get("dry_run", False))
    return False
