"""Unit tests for CLI commands."""

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from cocode import __version__
from cocode.__main__ import app

runner = CliRunner()


class TestMainCLI:
    """Test main CLI functionality."""

    def test_cli_help(self):
        """Test that help command works."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "cocode" in result.stdout
        assert "Orchestrate multiple code agents" in result.stdout

    def test_version_flag(self):
        """Test --version flag shows version."""
        result = runner.invoke(app, ["--version"])
        # The version flag uses typer.Exit() which the test runner sees as exit code 0
        assert result.exit_code == 0
        assert __version__ in result.output

    def test_no_args_shows_help(self):
        """Test that no args shows help."""
        result = runner.invoke(app, [])
        assert result.exit_code == 0
        assert "cocode" in result.output

    @pytest.mark.parametrize("log_level", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    def test_log_level_option(self, log_level):
        """Test --log-level option accepts valid levels."""
        # The callback is called during app initialization
        with patch("cocode.__main__.setup_logging") as mock_setup:
            result = runner.invoke(app, ["--log-level", log_level, "--help"])
            assert result.exit_code == 0
            mock_setup.assert_called_once_with(log_level)


class TestCommands:
    """Test individual command registration."""

    def test_init_command_exists(self):
        """Test that init command is registered."""
        result = runner.invoke(app, ["init", "--help"])
        assert result.exit_code == 0
        assert "init" in result.stdout

    def test_run_command_exists(self):
        """Test that run command is registered."""
        result = runner.invoke(app, ["run", "--help"])
        assert result.exit_code == 0
        assert "run" in result.stdout

    def test_doctor_command_exists(self):
        """Test that doctor command is registered."""
        result = runner.invoke(app, ["doctor", "--help"])
        assert result.exit_code == 0
        assert "doctor" in result.stdout

    def test_clean_command_exists(self):
        """Test that clean command is registered."""
        result = runner.invoke(app, ["clean", "--help"])
        assert result.exit_code == 0
        assert "clean" in result.stdout


class TestErrorHandling:
    """Test error handling in CLI."""

    def test_keyboard_interrupt_handling(self):
        """Test graceful handling of Ctrl+C."""
        with patch("cocode.__main__.app", side_effect=KeyboardInterrupt):
            from cocode.__main__ import main

            result = main()
            assert result == 130

    def test_general_exception_handling(self):
        """Test handling of unexpected exceptions."""
        with patch("cocode.__main__.app", side_effect=Exception("Test error")):
            from cocode.__main__ import main

            result = main()
            assert result == 1
