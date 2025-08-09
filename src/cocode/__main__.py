"""Entry point for cocode CLI."""

import sys
import typer
from rich.console import Console

from cocode.cli.init import init_command
from cocode.cli.run import run_command
from cocode.cli.doctor import doctor_command
from cocode.cli.clean import clean_command

app = typer.Typer(
    name="cocode",
    help="Orchestrate multiple code agents to fix GitHub issues",
    add_completion=True,
)
console = Console()

# Register commands
app.command("init")(init_command)
app.command("run")(run_command)
app.command("doctor")(doctor_command)
app.command("clean")(clean_command)


def main() -> int:
    """Main entry point for the CLI."""
    try:
        app()
        return 0
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        return 130
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1


if __name__ == "__main__":
    sys.exit(main())