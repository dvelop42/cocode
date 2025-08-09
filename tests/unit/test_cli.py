"""Unit tests for CLI commands."""

from typer.testing import CliRunner

from cocode.__main__ import app

runner = CliRunner()


def test_cli_help():
    """Test that help command works."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "cocode" in result.stdout
    assert "Orchestrate multiple code agents" in result.stdout


def test_init_command_exists():
    """Test that init command is registered."""
    result = runner.invoke(app, ["init", "--help"])
    assert result.exit_code == 0
    assert "init" in result.stdout


def test_run_command_exists():
    """Test that run command is registered."""
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    assert "run" in result.stdout


def test_doctor_command_exists():
    """Test that doctor command is registered."""
    result = runner.invoke(app, ["doctor", "--help"])
    assert result.exit_code == 0
    assert "doctor" in result.stdout


def test_clean_command_exists():
    """Test that clean command is registered."""
    result = runner.invoke(app, ["clean", "--help"])
    assert result.exit_code == 0
    assert "clean" in result.stdout
