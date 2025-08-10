"""Tests for Claude Code agent implementation."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from cocode.agents.claude_code import ClaudeCodeAgent


class TestClaudeCodeAgent:
    """Test suite for Claude Code agent."""

    @pytest.fixture
    def agent(self):
        """Create a Claude Code agent instance."""
        return ClaudeCodeAgent()

    def test_agent_initialization(self, agent):
        """Test agent initializes with correct name."""
        assert agent.name == "claude-code"
        assert agent.command_path is None

    @patch("shutil.which")
    def test_validate_environment_found(self, mock_which, agent):
        """Test environment validation when Claude CLI is found."""
        mock_which.return_value = "/usr/local/bin/claude"

        result = agent.validate_environment()

        assert result is True
        assert agent.command_path == "/usr/local/bin/claude"
        mock_which.assert_called_once_with("claude")

    @patch("shutil.which")
    def test_validate_environment_not_found(self, mock_which, agent):
        """Test environment validation when Claude CLI is not found."""
        mock_which.return_value = None

        result = agent.validate_environment()

        assert result is False
        assert agent.command_path is None
        mock_which.assert_called_once_with("claude")

    def test_prepare_environment_no_env_vars(self, agent):
        """Test environment preparation returns empty dict."""
        worktree_path = Path("/tmp/test")

        with patch.dict(os.environ, {}, clear=True):
            env = agent.prepare_environment(worktree_path, 123, "Issue body")

        # Should always return empty dict - Claude CLI handles its own env vars
        assert env == {}

    def test_prepare_environment_with_api_key(self, agent):
        """Test environment preparation with API key in environment."""
        worktree_path = Path("/tmp/test")

        with patch.dict(os.environ, {"CLAUDE_API_KEY": "test-key"}):
            env = agent.prepare_environment(worktree_path, 123, "Issue body")

        # Should return empty dict - Claude CLI reads API key directly from environment
        assert env == {}

    def test_prepare_environment_multiple_vars(self, agent):
        """Test environment preparation with multiple environment vars."""
        worktree_path = Path("/tmp/test")

        test_env = {
            "CLAUDE_API_KEY": "test-key",
            "ANTHROPIC_API_KEY": "anthropic-key",
            "CLAUDE_CODE_OAUTH_TOKEN": "oauth-token",
            "OTHER_VAR": "should-not-pass-through",
        }

        with patch.dict(os.environ, test_env):
            env = agent.prepare_environment(worktree_path, 123, "Issue body")

        # Should return empty dict - Claude CLI reads all vars directly from environment
        assert env == {}

    def test_get_command_basic(self, agent):
        """Test basic command generation."""
        agent.command_path = "/usr/local/bin/claude"

        with patch.dict(os.environ, {}, clear=True):
            command = agent.get_command()

        assert command == [
            "/usr/local/bin/claude",
            "code",
            "--non-interactive",
        ]

    @patch("shutil.which")
    def test_get_command_fallback(self, mock_which, agent):
        """Test command generation with fallback when command_path not set."""
        mock_which.return_value = "/usr/bin/claude"

        with patch.dict(os.environ, {}, clear=True):
            command = agent.get_command()

        assert agent.command_path == "/usr/bin/claude"
        assert command[0] == "/usr/bin/claude"

    @patch("shutil.which")
    def test_get_command_no_cli_raises_error(self, mock_which, agent):
        """Test that RuntimeError is raised when Claude CLI is not found."""
        mock_which.return_value = None

        with pytest.raises(RuntimeError, match="Claude CLI not found.*PATH"):
            agent.get_command()

    def test_get_command_with_issue_number(self, agent):
        """Test command generation with issue number in environment."""
        agent.command_path = "/usr/local/bin/claude"

        with patch.dict(os.environ, {"COCODE_ISSUE_NUMBER": "123"}):
            command = agent.get_command()

        # Command should be the same regardless of environment variables
        # Claude CLI reads them directly
        assert command == [
            "/usr/local/bin/claude",
            "code",
            "--non-interactive",
        ]

    def test_get_command_with_ready_marker(self, agent):
        """Test command generation with ready marker in environment."""
        agent.command_path = "/usr/local/bin/claude"

        with patch.dict(os.environ, {"COCODE_READY_MARKER": "ready for review"}):
            command = agent.get_command()

        # Command should be the same regardless of environment variables
        # Claude CLI reads them directly
        assert command == [
            "/usr/local/bin/claude",
            "code",
            "--non-interactive",
        ]

    def test_get_command_full(self, agent):
        """Test command generation with all environment variables."""
        agent.command_path = "/usr/local/bin/claude"

        test_env = {
            "COCODE_ISSUE_NUMBER": "456",
            "COCODE_READY_MARKER": "cocode ready for check",
            "COCODE_ISSUE_BODY_FILE": "/tmp/issue.txt",
        }

        with patch.dict(os.environ, test_env):
            command = agent.get_command()

        # Command remains simple - Claude CLI reads environment directly
        assert command == [
            "/usr/local/bin/claude",
            "code",
            "--non-interactive",
        ]

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

    def test_handle_error_authentication(self, agent):
        """Test error handling for authentication errors."""
        msg = agent.handle_error(1, "Authentication failed")
        assert "Authentication failed" in msg
        assert "CLAUDE_API_KEY" in msg

    def test_handle_error_rate_limit(self, agent):
        """Test error handling for rate limit errors."""
        msg = agent.handle_error(1, "Rate limit exceeded")
        assert "Rate limit exceeded" in msg

    def test_handle_error_network(self, agent):
        """Test error handling for network errors."""
        msg = agent.handle_error(1, "Network connection failed")
        assert "Network error" in msg

    def test_handle_error_permission(self, agent):
        """Test error handling for permission errors."""
        msg = agent.handle_error(1, "Permission denied")
        assert "Permission denied" in msg

    def test_check_ready_inherited(self, agent):
        """Test that check_ready is inherited from GitBasedAgent."""
        # Verify the agent has the check_ready method from parent
        assert hasattr(agent, "check_ready")
        assert callable(agent.check_ready)
