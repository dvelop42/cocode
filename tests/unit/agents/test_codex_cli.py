"""Tests for Codex CLI agent implementation."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from cocode.agents.codex_cli import CodexCliAgent


class TestCodexCliAgent:
    """Test suite for Codex CLI agent."""

    @pytest.fixture
    def agent(self):
        return CodexCliAgent()

    def test_agent_initialization(self, agent):
        assert agent.name == "codex-cli"
        assert agent.command_path is None

    @patch("shutil.which")
    def test_validate_environment_found(self, mock_which, agent):
        mock_which.return_value = "/usr/local/bin/codex"
        assert agent.validate_environment() is True
        assert agent.command_path == "/usr/local/bin/codex"
        mock_which.assert_called_once_with("codex")

    @patch("shutil.which")
    def test_validate_environment_not_found(self, mock_which, agent):
        mock_which.return_value = None
        assert agent.validate_environment() is False
        assert agent.command_path is None
        mock_which.assert_called_once_with("codex")

    def test_prepare_environment_no_env_vars(self, agent):
        worktree_path = Path("/tmp/test")
        with patch.dict(os.environ, {}, clear=True):
            env = agent.prepare_environment(worktree_path, 123, "Issue body")
        assert env == {}

    def test_prepare_environment_with_api_keys(self, agent):
        worktree_path = Path("/tmp/test")
        with patch.dict(
            os.environ,
            {"CODEX_API_KEY": "codex-key", "OPENAI_API_KEY": "openai-key"},
        ):
            env = agent.prepare_environment(worktree_path, 123, "Issue body")
        assert env == {}

    def test_get_command_basic(self, agent):
        agent.command_path = "/usr/local/bin/codex"
        with patch.dict(os.environ, {}, clear=True):
            command = agent.get_command()
        # No COCODE_* vars set means optional args may be omitted
        assert command[:2] == ["/usr/local/bin/codex", "fix"]
        assert "--no-interactive" in command

    def test_get_command_with_env(self, agent):
        agent.command_path = "/usr/local/bin/codex"
        test_env = {
            "COCODE_ISSUE_NUMBER": "456",
            "COCODE_READY_MARKER": "cocode ready for check",
            "COCODE_ISSUE_BODY_FILE": "/tmp/issue.txt",
        }
        with patch.dict(os.environ, test_env):
            command = agent.get_command()
        # Ensure flags and values are present
        assert command[0] == "/usr/local/bin/codex"
        assert "fix" in command
        assert "--issue-file" in command and "/tmp/issue.txt" in command
        assert "--issue-number" in command and "456" in command
        assert "--commit-marker" in command and "cocode ready for check" in command
        assert "--no-interactive" in command

    @patch("shutil.which")
    def test_get_command_fallback(self, mock_which, agent):
        mock_which.return_value = "/usr/bin/codex"
        with patch.dict(os.environ, {}, clear=True):
            command = agent.get_command()
        assert agent.command_path == "/usr/bin/codex"
        assert command[0] == "/usr/bin/codex"

    @patch("shutil.which")
    def test_get_command_no_cli_raises_error(self, mock_which, agent):
        mock_which.return_value = None
        with pytest.raises(RuntimeError, match="Codex CLI not found.*PATH"):
            agent.get_command()

    def test_handle_error_known_exit_codes(self, agent):
        assert "general error" in agent.handle_error(1, "").lower()
        assert "invalid configuration" in agent.handle_error(2, "").lower()
        assert "missing dependencies" in agent.handle_error(3, "").lower()
        assert "timed out" in agent.handle_error(124, "").lower()
        assert "interrupted" in agent.handle_error(130, "").lower()

    def test_handle_error_patterns(self, agent):
        msg = agent.handle_error(1, "Authentication failed: bad API key")
        assert "Authentication failed" in msg
        assert "CODEX_API_KEY" in msg or "OPENAI_API_KEY" in msg
        assert "rate limit" in agent.handle_error(1, "rate limit exceeded").lower()
        assert "network error" in agent.handle_error(1, "network connection lost").lower()
        assert "permission denied" in agent.handle_error(1, "Permission denied").lower()
        assert "model not found" in agent.handle_error(1, "model not found").lower()
        assert "token limit" in agent.handle_error(1, "token limit reached").lower()
