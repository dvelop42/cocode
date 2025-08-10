"""Tests for Codex CLI agent implementation."""

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cocode.agents.codex_cli import CodexCliAgent


class TestCodexCliAgent:
    """Test suite for Codex CLI agent."""

    @pytest.fixture
    def agent(self):
        """Create a Codex CLI agent instance."""
        return CodexCliAgent()

    def test_agent_initialization(self, agent):
        """Test agent initializes with correct name and attributes."""
        assert agent.name == "codex-cli"
        assert agent._command_path is None
        assert agent._cli_style is None

    @patch("shutil.which")
    @patch.object(CodexCliAgent, "_detect_cli_style")
    def test_validate_environment_found(self, mock_detect, mock_which, agent):
        """Test environment validation when Codex CLI is found."""
        mock_which.return_value = "/usr/local/bin/codex"
        mock_detect.return_value = "standard"

        result = agent.validate_environment()

        assert result is True
        assert agent._command_path == "/usr/local/bin/codex"
        assert agent._cli_style == "standard"
        mock_which.assert_called_once_with("codex")
        mock_detect.assert_called_once()

    @patch("shutil.which")
    def test_validate_environment_not_found(self, mock_which, agent):
        """Test environment validation when Codex CLI is not found."""
        mock_which.return_value = None

        result = agent.validate_environment()

        assert result is False
        assert agent._command_path is None
        mock_which.assert_called_once_with("codex")

    @patch("subprocess.run")
    def test_detect_cli_style_standard(self, mock_run, agent):
        """Test CLI style detection for standard interface."""
        agent._command_path = "/usr/local/bin/codex"
        mock_result = MagicMock()
        mock_result.stdout = "Commands:\n  fix    Fix issues\n  --issue-file    Specify issue file"
        mock_run.return_value = mock_result

        style = agent._detect_cli_style()

        assert style == "standard"
        mock_run.assert_called_once_with(
            ["/usr/local/bin/codex", "--help"], capture_output=True, text=True, timeout=5
        )

    @patch("subprocess.run")
    def test_detect_cli_style_env_based(self, mock_run, agent):
        """Test CLI style detection for environment-based interface."""
        agent._command_path = "/usr/local/bin/codex"
        mock_result = MagicMock()
        mock_result.stdout = "Codex CLI v1.0\nUsage: codex [options]"
        mock_run.return_value = mock_result

        style = agent._detect_cli_style()

        assert style == "env-based"

    @patch("subprocess.run")
    def test_detect_cli_style_timeout(self, mock_run, agent):
        """Test CLI style detection handles timeout gracefully."""
        agent._command_path = "/usr/local/bin/codex"
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["codex"], timeout=5)

        style = agent._detect_cli_style()

        assert style == "env-based"  # Falls back to env-based

    def test_detect_cli_style_no_command(self, agent):
        """Test CLI style detection when command path is not set."""
        agent._command_path = None

        style = agent._detect_cli_style()

        assert style == "env-based"

    def test_prepare_environment(self, agent):
        """Test environment preparation returns empty dict."""
        worktree_path = Path("/tmp/test")

        env = agent.prepare_environment(worktree_path, 123, "Issue body")

        assert env == {}

    @patch("pathlib.Path.exists")
    def test_validate_environment_variables_valid(self, mock_exists, agent):
        """Test environment variable validation with valid values."""
        mock_exists.return_value = True

        with patch.dict(
            os.environ,
            {
                "COCODE_ISSUE_BODY_FILE": "/tmp/issue.txt",
                "COCODE_ISSUE_NUMBER": "123",
                "COCODE_READY_MARKER": "cocode ready for check",
            },
        ):
            # Should not raise any exceptions
            agent._validate_environment_variables()

    @patch("pathlib.Path.exists")
    def test_validate_environment_variables_missing_file(self, mock_exists, agent):
        """Test environment variable validation with missing file."""
        mock_exists.return_value = False

        with patch.dict(
            os.environ,
            {
                "COCODE_ISSUE_BODY_FILE": "/tmp/missing.txt",
                "COCODE_ISSUE_NUMBER": "123",
                "COCODE_READY_MARKER": "cocode ready for check",
            },
        ):
            # Should raise RuntimeError with stricter validation
            with pytest.raises(RuntimeError, match="Issue file does not exist: /tmp/missing.txt"):
                agent._validate_environment_variables()

    def test_validate_environment_variables_invalid_number(self, agent):
        """Test environment variable validation with non-numeric issue number."""
        with patch.dict(
            os.environ,
            {
                "COCODE_ISSUE_NUMBER": "abc",
                "COCODE_ISSUE_BODY_FILE": "/tmp/issue.txt",
                "COCODE_READY_MARKER": "cocode ready for check",
            },
        ):
            # Should raise RuntimeError with stricter validation
            with pytest.raises(RuntimeError, match="Issue number is not numeric: abc"):
                agent._validate_environment_variables()

    def test_build_standard_command(self, agent):
        """Test building command for standard CLI interface."""
        agent._command_path = "/usr/local/bin/codex"

        with patch.dict(
            os.environ,
            {
                "COCODE_ISSUE_BODY_FILE": "/tmp/issue.txt",
                "COCODE_ISSUE_NUMBER": "123",
                "COCODE_READY_MARKER": "ready for review",
            },
        ):
            command = agent._build_standard_command()

        assert command == [
            "/usr/local/bin/codex",
            "fix",
            "--issue-file",
            "/tmp/issue.txt",
            "--issue-number",
            "123",
            "--no-interactive",
            "--commit-marker",
            "ready for review",
        ]

    def test_build_standard_command_minimal(self, agent):
        """Test building command with minimal environment variables."""
        agent._command_path = "/usr/local/bin/codex"

        with patch.dict(os.environ, {}, clear=True):
            command = agent._build_standard_command()

        assert command == ["/usr/local/bin/codex", "fix", "--no-interactive"]

    def test_build_env_based_command(self, agent):
        """Test building command for environment-based CLI."""
        agent._command_path = "/usr/local/bin/codex"

        command = agent._build_env_based_command()

        assert command == ["/usr/local/bin/codex"]

    @patch.object(CodexCliAgent, "_validate_environment_variables")
    @patch.object(CodexCliAgent, "_detect_cli_style")
    @patch.object(CodexCliAgent, "_build_standard_command")
    def test_get_command_standard_style(self, mock_build, mock_detect, mock_validate, agent):
        """Test get_command with standard CLI style."""
        agent._command_path = "/usr/local/bin/codex"
        agent._cli_style = "standard"
        mock_build.return_value = ["codex", "fix"]

        command = agent.get_command()

        assert command == ["codex", "fix"]
        mock_validate.assert_called_once()
        mock_build.assert_called_once()

    @patch.object(CodexCliAgent, "_validate_environment_variables")
    @patch.object(CodexCliAgent, "_build_env_based_command")
    def test_get_command_env_based_style(self, mock_build, mock_validate, agent):
        """Test get_command with environment-based CLI style."""
        agent._command_path = "/usr/local/bin/codex"
        agent._cli_style = "env-based"
        mock_build.return_value = ["codex"]

        command = agent.get_command()

        assert command == ["codex"]
        mock_validate.assert_called_once()
        mock_build.assert_called_once()

    @patch("shutil.which")
    @patch.object(CodexCliAgent, "_detect_cli_style")
    def test_get_command_fallback(self, mock_detect, mock_which, agent):
        """Test get_command with fallback when command_path not set."""
        mock_which.return_value = "/usr/bin/codex"
        mock_detect.return_value = "env-based"

        with patch.object(agent, "_validate_environment_variables"):
            with patch.object(agent, "_build_env_based_command") as mock_build:
                mock_build.return_value = ["codex"]
                command = agent.get_command()

        assert agent._command_path == "/usr/bin/codex"
        assert command == ["codex"]

    @patch("shutil.which")
    def test_get_command_no_cli_raises_error(self, mock_which, agent):
        """Test that RuntimeError is raised when Codex CLI is not found."""
        mock_which.return_value = None

        with pytest.raises(RuntimeError, match="Codex CLI.*not found.*PATH"):
            agent.get_command()

    def test_handle_error_known_exit_codes(self, agent):
        """Test error handling for known exit codes."""
        assert "general error" in agent.handle_error(1, "").lower()
        assert "invalid configuration" in agent.handle_error(2, "").lower()
        assert "missing dependencies" in agent.handle_error(3, "").lower()
        assert "timed out" in agent.handle_error(124, "").lower()
        assert "interrupted" in agent.handle_error(130, "").lower()

    def test_handle_error_unknown_exit_code(self, agent):
        """Test error handling for unknown exit codes."""
        msg = agent.handle_error(99, "")
        assert "exit code 99" in msg

    def test_handle_error_authentication_codex_key(self, agent):
        """Test error handling for CODEX_API_KEY authentication errors."""
        msg = agent.handle_error(1, "Error: codex_api_key not found, api key missing")
        assert "CODEX_API_KEY is missing or invalid" in msg

    def test_handle_error_authentication_openai_key(self, agent):
        """Test error handling for OPENAI_API_KEY authentication errors."""
        msg = agent.handle_error(1, "Error: openai_api_key not found, api key missing")
        assert "OPENAI_API_KEY is missing or invalid" in msg

    def test_handle_error_authentication_unauthorized(self, agent):
        """Test error handling for unauthorized errors."""
        msg = agent.handle_error(1, "401 Unauthorized API key")
        assert "API key is invalid or expired" in msg

    def test_handle_error_authentication_generic(self, agent):
        """Test error handling for generic authentication errors."""
        msg = agent.handle_error(1, "Authentication failed")
        assert "Check CODEX_API_KEY or OPENAI_API_KEY" in msg

    def test_handle_error_rate_limit_quota(self, agent):
        """Test error handling for quota exceeded errors."""
        msg = agent.handle_error(1, "Rate limit: quota exceeded")
        assert "API quota exceeded" in msg

    def test_handle_error_rate_limit_generic(self, agent):
        """Test error handling for generic rate limit errors."""
        msg = agent.handle_error(1, "Rate limit exceeded")
        assert "Please wait before retrying" in msg

    def test_handle_error_network_timeout(self, agent):
        """Test error handling for network timeout errors."""
        msg = agent.handle_error(1, "Network timeout occurred")
        assert "API server might be slow or unreachable" in msg

    def test_handle_error_network_refused(self, agent):
        """Test error handling for connection refused errors."""
        msg = agent.handle_error(1, "Connection refused")
        assert "firewall or proxy" in msg

    def test_handle_error_network_generic(self, agent):
        """Test error handling for generic network errors."""
        msg = agent.handle_error(1, "Network error")
        assert "Check your internet connection" in msg

    def test_handle_error_permission(self, agent):
        """Test error handling for permission errors."""
        msg = agent.handle_error(1, "Permission denied")
        assert "Check file permissions in worktree" in msg

    def test_handle_error_model_not_found(self, agent):
        """Test error handling for model not found errors."""
        msg = agent.handle_error(1, "Model not found")
        assert "Check CODEX_MODEL environment variable" in msg

    def test_handle_error_model_deprecated(self, agent):
        """Test error handling for deprecated model errors."""
        msg = agent.handle_error(1, "Model deprecated")
        assert "Update CODEX_MODEL to a supported model" in msg

    def test_handle_error_token_limit(self, agent):
        """Test error handling for token limit errors."""
        msg = agent.handle_error(1, "Token limit exceeded")
        assert "Try reducing CODEX_MAX_TOKENS" in msg

    def test_check_ready_inherited(self, agent):
        """Test that check_ready is inherited from GitBasedAgent."""
        # Verify the agent has the check_ready method from parent
        assert hasattr(agent, "check_ready")
        assert callable(agent.check_ready)
