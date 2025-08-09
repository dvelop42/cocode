# ADR-002: CLI Framework Selection

**Status**: Proposed → **ACCEPTED** ✅

**Date**: 2024-01-09

**Decision**: **Typer**

## Context

We need to choose a CLI framework for cocode that will handle command parsing, help generation, and user interaction. The framework must support:
- Subcommands (init, run, doctor, clean)
- Interactive prompts
- Progress indicators
- Type safety
- Testing

## Options Evaluated

### Option 1: Click
```python
import click

@click.group()
@click.version_option()
def cli():
    """cocode - orchestrate code agents"""
    pass

@cli.command()
@click.option('--agents', multiple=True)
def init(agents):
    """Initialize cocode configuration"""
    pass
```

**Pros:**
- ✅ Battle-tested (used by Flask, Black, many others)
- ✅ Extensive plugin ecosystem
- ✅ Excellent documentation
- ✅ Supports complex command structures

**Cons:**
- ❌ Verbose syntax
- ❌ Decorators can be confusing
- ❌ No built-in type hints support
- ❌ Manual shell completion setup

### Option 2: Typer
```python
import typer
from typing import List, Optional

app = typer.Typer()

@app.command()
def init(
    agents: Optional[List[str]] = typer.Option(None, help="Agents to use"),
    interactive: bool = typer.Option(True, help="Interactive mode")
):
    """Initialize cocode configuration"""
    if not agents and interactive:
        agents = prompt_for_agents()
    save_config(agents)
```

**Pros:**
- ✅ Built on Click (inherits stability)
- ✅ Modern Python with type hints
- ✅ Auto-generates shell completion
- ✅ Cleaner, more Pythonic syntax
- ✅ Automatic help from docstrings and types
- ✅ Better IDE support

**Cons:**
- ❌ Smaller community
- ❌ Fewer third-party extensions
- ❌ Less battle-tested

## Decision

**Choose Typer** for the following reasons:

1. **Type Safety**: Native type hints improve code quality and IDE support
2. **Developer Experience**: Cleaner syntax reduces boilerplate
3. **Auto-completion**: Built-in shell completion generation
4. **Modern Patterns**: Aligns with Python 3.10+ best practices
5. **Click Foundation**: Built on Click, so we can drop down to Click if needed

## Implementation Example

```python
# src/cocode/cli/__init__.py
import typer
from pathlib import Path
from typing import Optional, List
from rich.console import Console
from rich.prompt import Confirm, Prompt

from cocode.config import ConfigManager
from cocode.doctor import run_diagnostics

app = typer.Typer(
    name="cocode",
    help="Orchestrate multiple code agents to fix GitHub issues",
    add_completion=True,
)
console = Console()

@app.command()
def init(
    agents: Optional[List[str]] = typer.Option(
        None, 
        "--agent", "-a",
        help="Agents to enable (can be used multiple times)"
    ),
    base_agent: Optional[str] = typer.Option(
        None,
        "--base", "-b",
        help="Base agent for recommendations"
    ),
    interactive: bool = typer.Option(
        True,
        "--interactive/--no-interactive",
        help="Interactive mode"
    ),
):
    """Initialize cocode configuration"""
    config = ConfigManager()
    
    if interactive and not agents:
        # Interactive selection
        from cocode.agents.discovery import discover_agents
        available = discover_agents()
        
        if not available:
            console.print("[red]No agents found![/red]")
            raise typer.Exit(1)
        
        # Multi-select prompt
        agents = select_agents(available)
        
    if interactive and not base_agent:
        base_agent = select_base_agent(agents)
    
    config.save(agents=agents, base_agent=base_agent)
    console.print(f"[green]✓[/green] Configuration saved to {config.path}")

@app.command()
def run(
    repo: Optional[Path] = typer.Argument(
        None,
        help="Repository path (auto-detect if not provided)"
    ),
    issue: Optional[int] = typer.Option(
        None,
        "--issue", "-i",
        help="Issue number to work on"
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview without making changes"
    ),
):
    """Run agents on a GitHub issue"""
    from cocode.orchestrator import Orchestrator
    
    orchestrator = Orchestrator(dry_run=dry_run)
    orchestrator.run(repo=repo, issue=issue)

@app.command()
def doctor():
    """Check system dependencies and configuration"""
    results = run_diagnostics()
    
    for check in results:
        status = "✓" if check.passed else "✗"
        color = "green" if check.passed else "red"
        console.print(f"[{color}]{status}[/{color}] {check.name}: {check.message}")
    
    if not all(r.passed for r in results):
        raise typer.Exit(1)

@app.command()
def clean(
    hard: bool = typer.Option(
        False,
        "--hard",
        help="Remove unmerged worktrees (with confirmation)"
    ),
    yes: bool = typer.Option(
        False,
        "--yes", "-y",
        help="Skip confirmation prompts"
    ),
):
    """Clean up cocode worktrees and state"""
    from cocode.cleanup import CleanupManager
    
    cleanup = CleanupManager()
    items = cleanup.find_items(include_unmerged=hard)
    
    if not items:
        console.print("Nothing to clean")
        return
    
    # Show what will be removed
    for item in items:
        console.print(f"  - {item}")
    
    if not yes:
        if not Confirm.ask("Remove these items?"):
            raise typer.Abort()
    
    cleanup.clean(items)
    console.print(f"[green]✓[/green] Cleaned {len(items)} items")

if __name__ == "__main__":
    app()
```

## Testing Strategy

```python
# tests/test_cli.py
from typer.testing import CliRunner
from cocode.cli import app

runner = CliRunner()

def test_init_command():
    result = runner.invoke(app, ["init", "--no-interactive", "--agent", "claude-code"])
    assert result.exit_code == 0
    assert "Configuration saved" in result.output

def test_doctor_command():
    result = runner.invoke(app, ["doctor"])
    # Exit code depends on system state
    assert "✓" in result.output or "✗" in result.output
```

## Migration Path

Not applicable (new project).

## Consequences

### Positive
- Clean, maintainable CLI code
- Excellent IDE support and type checking
- Automatic shell completion for users
- Easy to test with typer.testing.CliRunner
- Good documentation generation

### Negative
- Fewer examples and Stack Overflow answers
- May need to drop to Click for advanced features
- Team needs to learn Typer patterns

### Mitigation
- Typer is built on Click, so Click knowledge transfers
- Can use Click directly for complex cases
- Typer documentation is excellent

## References
- [Typer Documentation](https://typer.tiangolo.com/)
- [Click Documentation](https://click.palletsprojects.com/)
- [FastAPI CLI uses Typer](https://github.com/tiangolo/fastapi-cli)