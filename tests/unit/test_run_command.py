"""Tests for the run CLI factory and dry-run path."""

from typer.testing import CliRunner

from cocode.__main__ import app
from cocode.agents.claude_code import ClaudeCodeAgent
from cocode.agents.codex_cli import CodexCliAgent
from cocode.agents.default import GitBasedAgent
from cocode.cli.run import create_agent

runner = CliRunner()


def test_create_agent_factory_mappings():
    """Factory returns proper agent implementations."""
    assert isinstance(create_agent("claude-code"), ClaudeCodeAgent)
    assert isinstance(create_agent("codex-cli"), CodexCliAgent)
    # Unknown agent name falls back to generic git-based agent
    assert isinstance(create_agent("unknown"), GitBasedAgent)


def test_run_command_dry_run_executes_without_side_effects():
    """Invoking run in dry-run mode should succeed and print plan."""
    # Use the top-level app so the global --dry-run flag is handled
    result = runner.invoke(app, ["--dry-run", "run", "123", "--no-tui"])  # type: ignore[arg-type]
    assert result.exit_code == 0
    # Expect dry run banner and steps
    assert "DRY RUN MODE" in result.stdout
    assert "Would run agents on issue #123" in result.stdout
    assert "Operations that would be performed" in result.stdout
