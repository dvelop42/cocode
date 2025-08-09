"""Unit tests for the init command."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from cocode.__main__ import app
from cocode.agents.discovery import AgentInfo
from cocode.config.manager import ConfigurationError
from cocode.utils.exit_codes import ExitCode


@pytest.fixture
def runner():
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def mock_agents():
    """Create mock discovered agents."""
    return [
        AgentInfo(name="claude-code", installed=True, path="/usr/bin/claude", aliases=["claude"]),
        AgentInfo(name="codex-cli", installed=True, path="/usr/bin/codex", aliases=["codex"]),
        AgentInfo(name="other-agent", installed=False, path=None, aliases=["other"]),
    ]


@pytest.fixture
def mock_no_agents():
    """Create mock with no agents installed."""
    return [
        AgentInfo(name="claude-code", installed=False, path=None, aliases=["claude"]),
        AgentInfo(name="codex-cli", installed=False, path=None, aliases=["codex"]),
    ]


class TestInitCommand:
    """Test suite for init command."""

    def test_init_non_interactive_with_agents(self, runner, mock_agents, tmp_path):
        """Test non-interactive mode with available agents."""
        with patch("cocode.cli.init.Path") as mock_path:
            mock_config_path = tmp_path / ".cocode" / "config.json"
            mock_path.return_value = mock_config_path

            with patch("cocode.cli.init.discover_agents", return_value=mock_agents):
                with patch("cocode.cli.init.ConfigManager") as mock_config_manager:
                    mock_manager = MagicMock()
                    mock_config_manager.return_value = mock_manager

                    # Run in non-interactive mode
                    with patch("sys.exit") as mock_exit:
                        result = runner.invoke(app, ["init", "--no-interactive"])

                        # Check that sys.exit was called with success
                        mock_exit.assert_called_once_with(ExitCode.SUCCESS)

                    # Verify config manager interactions
                    mock_manager.load.assert_called_once()
                    mock_manager.set.assert_any_call(
                        "agents",
                        [
                            {"name": "claude-code", "command": "claude", "args": []},
                            {"name": "codex-cli", "command": "codex", "args": []},
                        ],
                    )
                    mock_manager.set.assert_any_call("base_agent", "claude-code")
                    mock_manager.save.assert_called_once()

                    # Check output contains success messages
                    assert "Configuring 2 available agent(s) with defaults" in result.output
                    assert "Configuration saved" in result.output

    def test_init_interactive_mode_single_agent(self, runner, tmp_path):
        """Test interactive mode with single agent selection."""
        mock_single_agent = [
            AgentInfo(
                name="claude-code", installed=True, path="/usr/bin/claude", aliases=["claude"]
            ),
        ]

        with patch("cocode.cli.init.Path") as mock_path:
            mock_config_path = tmp_path / ".cocode" / "config.json"
            mock_path.return_value = mock_config_path

            with patch("cocode.cli.init.discover_agents", return_value=mock_single_agent):
                with patch("cocode.cli.init.ConfigManager") as mock_config_manager:
                    mock_manager = MagicMock()
                    mock_config_manager.return_value = mock_manager

                    # Mock user interactions
                    with patch(
                        "cocode.cli.init.Confirm.ask", side_effect=[True, False]
                    ):  # Configure agent, no custom args
                        with patch(
                            "cocode.cli.init.Prompt.ask", return_value="claude"
                        ):  # Use default command
                            with patch("sys.exit") as mock_exit:
                                result = runner.invoke(app, ["init"])

                                mock_exit.assert_called_once_with(ExitCode.SUCCESS)

                    # Verify single agent was configured as base
                    mock_manager.set.assert_any_call("base_agent", "claude-code")
                    assert "Using claude-code as base agent" in result.output

    def test_init_no_agents_available(self, runner, mock_no_agents, tmp_path):
        """Test behavior when no agents are found."""
        with patch("cocode.cli.init.Path") as mock_path:
            mock_config_path = tmp_path / ".cocode" / "config.json"
            mock_path.return_value = mock_config_path

            with patch("cocode.cli.init.discover_agents", return_value=mock_no_agents):
                result = runner.invoke(app, ["init", "--no-interactive"])

                # Should exit with missing deps code
                assert result.exit_code == ExitCode.MISSING_DEPS
                assert "No agents found on PATH" in result.output
                assert "Install one of the following agents" in result.output

    def test_init_force_overwrite(self, runner, mock_agents, tmp_path):
        """Test --force flag overwrites existing configuration."""
        config_path = tmp_path / ".cocode" / "config.json"
        config_path.parent.mkdir(parents=True)
        config_path.write_text('{"version": "1.0.0"}')

        with patch("cocode.cli.init.Path") as mock_path:
            mock_path.return_value = config_path

            with patch("cocode.cli.init.discover_agents", return_value=mock_agents):
                with patch("cocode.cli.init.ConfigManager") as mock_config_manager:
                    mock_manager = MagicMock()
                    mock_config_manager.return_value = mock_manager

                    with patch("sys.exit") as mock_exit:
                        runner.invoke(app, ["init", "--no-interactive", "--force"])

                        mock_exit.assert_called_once_with(ExitCode.SUCCESS)
                        mock_manager.save.assert_called_once()

    def test_init_existing_config_no_force(self, runner, tmp_path):
        """Test behavior with existing config and no --force flag."""
        config_path = tmp_path / ".cocode" / "config.json"
        config_path.parent.mkdir(parents=True)
        config_path.write_text('{"version": "1.0.0"}')

        with patch("cocode.cli.init.Path") as mock_path:
            mock_path.return_value = config_path

            result = runner.invoke(app, ["init", "--no-interactive"])

            assert result.exit_code == ExitCode.GENERAL_ERROR
            assert "Configuration already exists" in result.output
            assert "Use --force to overwrite" in result.output

    def test_init_interactive_decline_overwrite(self, runner, tmp_path):
        """Test interactive mode when user declines to overwrite existing config."""
        config_path = tmp_path / ".cocode" / "config.json"
        config_path.parent.mkdir(parents=True)
        config_path.write_text('{"version": "1.0.0"}')

        with patch("cocode.cli.init.Path") as mock_path:
            mock_path.return_value = config_path

            with patch(
                "cocode.cli.init.Confirm.ask", return_value=False
            ):  # User says no to overwrite
                with patch("sys.exit") as mock_exit:
                    result = runner.invoke(app, ["init"])

                    mock_exit.assert_called_once_with(ExitCode.SUCCESS)
                    assert "Keeping existing configuration" in result.output

    def test_init_custom_arguments_with_quotes(self, runner, mock_agents, tmp_path):
        """Test handling of quoted arguments in interactive mode."""
        with patch("cocode.cli.init.Path") as mock_path:
            mock_config_path = tmp_path / ".cocode" / "config.json"
            mock_path.return_value = mock_config_path

            with patch("cocode.cli.init.discover_agents", return_value=mock_agents):
                with patch("cocode.cli.init.ConfigManager") as mock_config_manager:
                    mock_manager = MagicMock()
                    mock_config_manager.return_value = mock_manager

                    # Mock user interactions
                    with patch(
                        "cocode.cli.init.Confirm.ask",
                        side_effect=[
                            True,  # Configure claude-code
                            True,  # Add custom arguments
                            False,  # Don't configure codex-cli
                        ],
                    ):
                        with patch(
                            "cocode.cli.init.Prompt.ask",
                            side_effect=[
                                "claude",  # Command
                                '--flag "value with spaces" --another-flag',  # Arguments with quotes
                            ],
                        ):
                            with patch("sys.exit") as mock_exit:
                                runner.invoke(app, ["init"])

                                mock_exit.assert_called_once_with(ExitCode.SUCCESS)

                    # Verify arguments were properly parsed with shlex
                    call_args = mock_manager.set.call_args_list
                    agents_call = [call for call in call_args if call[0][0] == "agents"][0]
                    agents = agents_call[0][1]

                    assert agents[0]["args"] == ["--flag", "value with spaces", "--another-flag"]

    def test_init_invalid_argument_format(self, runner, mock_agents, tmp_path):
        """Test handling of invalid argument format."""
        with patch("cocode.cli.init.Path") as mock_path:
            mock_config_path = tmp_path / ".cocode" / "config.json"
            mock_path.return_value = mock_config_path

            with patch("cocode.cli.init.discover_agents", return_value=mock_agents):
                with patch("cocode.cli.init.ConfigManager") as mock_config_manager:
                    mock_manager = MagicMock()
                    mock_config_manager.return_value = mock_manager

                    with patch("cocode.cli.init.Confirm.ask", side_effect=[True, True, False]):
                        with patch(
                            "cocode.cli.init.Prompt.ask",
                            side_effect=[
                                "claude",  # Command
                                'unclosed "quote',  # Invalid arguments
                            ],
                        ):
                            with patch("sys.exit") as mock_exit:
                                result = runner.invoke(app, ["init"])

                                mock_exit.assert_called_once_with(ExitCode.SUCCESS)
                                assert "Warning: Invalid argument format" in result.output

                    # Verify empty args list was set for invalid input
                    call_args = mock_manager.set.call_args_list
                    agents_call = [call for call in call_args if call[0][0] == "agents"][0]
                    agents = agents_call[0][1]
                    assert agents[0]["args"] == []

    def test_init_multiple_agents_base_selection(self, runner, mock_agents, tmp_path):
        """Test base agent selection with multiple agents."""
        with patch("cocode.cli.init.Path") as mock_path:
            mock_config_path = tmp_path / ".cocode" / "config.json"
            mock_path.return_value = mock_config_path

            with patch("cocode.cli.init.discover_agents", return_value=mock_agents):
                with patch("cocode.cli.init.ConfigManager") as mock_config_manager:
                    mock_manager = MagicMock()
                    mock_config_manager.return_value = mock_manager

                    with patch(
                        "cocode.cli.init.Confirm.ask",
                        side_effect=[
                            True,
                            False,  # Configure claude-code, no args
                            True,
                            False,  # Configure codex-cli, no args
                        ],
                    ):
                        with patch(
                            "cocode.cli.init.Prompt.ask",
                            side_effect=[
                                "claude",  # Command for claude-code
                                "codex",  # Command for codex-cli
                                "2",  # Choose codex-cli as base (option 2)
                            ],
                        ):
                            with patch("sys.exit") as mock_exit:
                                runner.invoke(app, ["init"])

                                mock_exit.assert_called_once_with(ExitCode.SUCCESS)

                    # Verify codex-cli was set as base agent
                    mock_manager.set.assert_any_call("base_agent", "codex-cli")

    def test_init_configuration_error_handling(self, runner, mock_agents, tmp_path):
        """Test handling of ConfigurationError."""
        with patch("cocode.cli.init.Path") as mock_path:
            mock_config_path = tmp_path / ".cocode" / "config.json"
            mock_path.return_value = mock_config_path

            with patch("cocode.cli.init.discover_agents", return_value=mock_agents):
                with patch("cocode.cli.init.ConfigManager") as mock_config_manager:
                    mock_manager = MagicMock()
                    mock_manager.save.side_effect = ConfigurationError("Test error")
                    mock_config_manager.return_value = mock_manager

                    result = runner.invoke(app, ["init", "--no-interactive"])

                    assert result.exit_code == ExitCode.GENERAL_ERROR
                    assert "Failed to save configuration: Test error" in result.output

    def test_init_unexpected_error_handling(self, runner, mock_agents, tmp_path):
        """Test handling of unexpected exceptions."""
        with patch("cocode.cli.init.Path") as mock_path:
            mock_config_path = tmp_path / ".cocode" / "config.json"
            mock_path.return_value = mock_config_path

            with patch("cocode.cli.init.discover_agents", return_value=mock_agents):
                with patch("cocode.cli.init.ConfigManager") as mock_config_manager:
                    mock_manager = MagicMock()
                    mock_manager.save.side_effect = Exception("Unexpected error")
                    mock_config_manager.return_value = mock_manager

                    result = runner.invoke(app, ["init", "--no-interactive"])

                    assert result.exit_code == ExitCode.GENERAL_ERROR
                    assert "Unexpected error" in result.output

    def test_init_no_agents_selected_interactive(self, runner, mock_agents, tmp_path):
        """Test when user selects no agents in interactive mode."""
        with patch("cocode.cli.init.Path") as mock_path:
            mock_config_path = tmp_path / ".cocode" / "config.json"
            mock_path.return_value = mock_config_path

            with patch("cocode.cli.init.discover_agents", return_value=mock_agents):
                with patch(
                    "cocode.cli.init.Confirm.ask", return_value=False
                ):  # Don't configure any agents
                    result = runner.invoke(app, ["init"])

                    assert result.exit_code == ExitCode.GENERAL_ERROR
                    assert "No agents selected" in result.output
