"""Unit tests for AgentFactory."""

from __future__ import annotations

import subprocess
from unittest.mock import Mock, patch

import pytest

from cocode.agents.base import Agent
from cocode.agents.claude_code import ClaudeCodeAgent
from cocode.agents.codex_cli import CodexCliAgent
from cocode.agents.default import GitBasedAgent
from cocode.agents.factory import AgentFactory, AgentFactoryError, DependencyError
from cocode.config.manager import ConfigManager


@pytest.fixture
def mock_config_manager():
    """Create a mock config manager."""
    manager = Mock(spec=ConfigManager)
    manager.get_agent.return_value = None
    manager.list_agents.return_value = []
    return manager


@pytest.fixture
def factory(mock_config_manager):
    """Create an agent factory with mock config manager."""
    return AgentFactory(config_manager=mock_config_manager)


class TestAgentFactory:
    """Test AgentFactory class."""

    def test_init_default(self):
        """Test factory initialization with default config manager."""
        factory = AgentFactory()
        assert factory.config_manager is not None
        assert isinstance(factory.config_manager, ConfigManager)

    def test_init_with_config_manager(self, mock_config_manager):
        """Test factory initialization with provided config manager."""
        factory = AgentFactory(config_manager=mock_config_manager)
        assert factory.config_manager is mock_config_manager

    @patch("cocode.agents.factory.which_agent")
    @patch("cocode.agents.factory.shutil.which")
    def test_create_claude_code_agent(self, mock_which, mock_which_agent, factory):
        """Test creating a Claude Code agent."""
        mock_which_agent.return_value = "/usr/local/bin/claude"
        mock_which.side_effect = lambda cmd: {
            "claude": "/usr/local/bin/claude",
            "git": "/usr/bin/git",
            "gh": "/usr/local/bin/gh",
        }.get(cmd)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="Claude CLI v1.0.0")

            agent = factory.create_agent("claude-code")

            assert isinstance(agent, ClaudeCodeAgent)
            mock_which_agent.assert_called_once_with("claude-code")

    @patch("cocode.agents.factory.which_agent")
    @patch("cocode.agents.factory.shutil.which")
    def test_create_codex_cli_agent(self, mock_which, mock_which_agent, factory):
        """Test creating a Codex CLI agent."""
        mock_which_agent.return_value = "/usr/local/bin/codex"
        mock_which.side_effect = lambda cmd: {
            "codex": "/usr/local/bin/codex",
            "git": "/usr/bin/git",
            "gh": "/usr/local/bin/gh",
        }.get(cmd)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="Codex CLI v1.0.0")

            agent = factory.create_agent("codex-cli")

            assert isinstance(agent, CodexCliAgent)
            mock_which_agent.assert_called_once_with("codex-cli")

    @patch("cocode.agents.factory.which_agent")
    @patch("cocode.agents.factory.shutil.which")
    def test_create_custom_agent(self, mock_which, mock_which_agent, factory):
        """Test creating a custom agent not in registry."""
        mock_which_agent.return_value = None
        mock_which.side_effect = lambda cmd: {
            "custom-agent": "/usr/local/bin/custom-agent",
            "git": "/usr/bin/git",
            "gh": "/usr/local/bin/gh",
        }.get(cmd)

        factory.config_manager.get_agent.return_value = {
            "name": "custom-agent",
            "command": "custom-agent",
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)

            agent = factory.create_agent("custom-agent")

            assert isinstance(agent, GitBasedAgent)
            assert agent.name == "custom-agent"

    @patch("cocode.agents.factory.which_agent")
    @patch("cocode.agents.factory.shutil.which")
    def test_create_agent_with_config_override(self, mock_which, mock_which_agent, factory):
        """Test creating an agent with configuration override."""
        mock_which_agent.return_value = "/usr/local/bin/claude"
        mock_which.side_effect = lambda cmd: {
            "claude": "/usr/local/bin/claude",
            "git": "/usr/bin/git",
            "gh": "/usr/local/bin/gh",
        }.get(cmd)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)

            config_override = {"timeout": 1800}
            agent = factory.create_agent("claude-code", config_override=config_override)

            assert isinstance(agent, ClaudeCodeAgent)

    @patch("cocode.agents.factory.which_agent")
    @patch("cocode.agents.factory.shutil.which")
    def test_create_agent_skip_validation(self, mock_which, mock_which_agent, factory):
        """Test creating an agent without dependency validation."""
        mock_which_agent.return_value = None
        mock_which.return_value = None

        agent = factory.create_agent("claude-code", validate_dependencies=False)

        assert isinstance(agent, ClaudeCodeAgent)
        # which_agent should not be called when validation is skipped
        mock_which_agent.assert_not_called()

    @patch("cocode.agents.factory.which_agent")
    @patch("cocode.agents.factory.shutil.which")
    def test_create_agent_missing_binary(self, mock_which, mock_which_agent, factory):
        """Test creating an agent when binary is missing."""
        mock_which_agent.return_value = None
        mock_which.side_effect = lambda cmd: {
            "git": "/usr/bin/git",
            "gh": "/usr/local/bin/gh",
        }.get(cmd)

        with pytest.raises(DependencyError) as exc_info:
            factory.create_agent("claude-code")

        assert "claude-code" in str(exc_info.value)
        assert "not found on PATH" in str(exc_info.value)

    @patch("cocode.agents.factory.shutil.which")
    def test_create_agent_missing_git(self, mock_which, factory):
        """Test creating an agent when git is missing."""
        mock_which.side_effect = lambda cmd: {
            "claude": "/usr/local/bin/claude",
            "gh": "/usr/local/bin/gh",
        }.get(cmd)

        with pytest.raises(DependencyError) as exc_info:
            factory.create_agent("claude-code")

        assert "Git is not installed" in str(exc_info.value)

    @patch("cocode.agents.factory.shutil.which")
    def test_create_agent_missing_gh(self, mock_which, factory):
        """Test creating an agent when gh CLI is missing."""
        mock_which.side_effect = lambda cmd: {
            "claude": "/usr/local/bin/claude",
            "git": "/usr/bin/git",
        }.get(cmd)

        with pytest.raises(DependencyError) as exc_info:
            factory.create_agent("claude-code")

        assert "GitHub CLI (gh) is not installed" in str(exc_info.value)

    @patch("cocode.agents.factory.shutil.which")
    def test_create_agent_gh_not_authenticated(self, mock_which, factory):
        """Test creating an agent when gh is not authenticated."""
        mock_which.side_effect = lambda cmd: {
            "claude": "/usr/local/bin/claude",
            "git": "/usr/bin/git",
            "gh": "/usr/local/bin/gh",
        }.get(cmd)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="", stderr="Not authenticated")

            with pytest.raises(DependencyError) as exc_info:
                factory.create_agent("claude-code")

            assert "GitHub CLI not authenticated" in str(exc_info.value)

    @patch("cocode.agents.factory.which_agent")
    @patch("cocode.agents.factory.shutil.which")
    def test_create_agents_all_configured(self, mock_which, mock_which_agent, factory):
        """Test creating all configured agents."""
        mock_which_agent.return_value = "/usr/local/bin/agent"
        mock_which.return_value = "/usr/local/bin/cmd"

        factory.config_manager.list_agents.return_value = [
            {"name": "agent1", "command": "agent1"},
            {"name": "agent2", "command": "agent2"},
        ]

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)

            agents = factory.create_agents()

            assert len(agents) == 2
            assert "agent1" in agents
            assert "agent2" in agents
            assert all(isinstance(agent, GitBasedAgent) for agent in agents.values())

    @patch("cocode.agents.factory.which_agent")
    @patch("cocode.agents.factory.shutil.which")
    def test_create_agents_specific_list(self, mock_which, mock_which_agent, factory):
        """Test creating specific agents from a list."""
        mock_which_agent.return_value = "/usr/local/bin/claude"
        mock_which.side_effect = lambda cmd: {
            "claude": "/usr/local/bin/claude",
            "codex": "/usr/local/bin/codex",
            "git": "/usr/bin/git",
            "gh": "/usr/local/bin/gh",
        }.get(cmd)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)

            agents = factory.create_agents(["claude-code", "codex-cli"])

            assert len(agents) == 2
            assert isinstance(agents["claude-code"], ClaudeCodeAgent)
            assert isinstance(agents["codex-cli"], CodexCliAgent)

    @patch("cocode.agents.factory.which_agent")
    @patch("cocode.agents.factory.shutil.which")
    def test_create_agents_with_failures(self, mock_which, mock_which_agent, factory):
        """Test creating agents when some fail."""
        mock_which_agent.side_effect = ["/usr/local/bin/claude", None]
        mock_which.side_effect = lambda cmd: {
            "claude": "/usr/local/bin/claude",
            "git": "/usr/bin/git",
            "gh": "/usr/local/bin/gh",
        }.get(cmd)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)

            with pytest.raises(AgentFactoryError) as exc_info:
                factory.create_agents(["claude-code", "codex-cli"])

            assert "Failed to create some agents" in str(exc_info.value)
            assert "codex-cli" in str(exc_info.value)

    @patch("cocode.agents.factory.which_agent")
    @patch("cocode.agents.factory.shutil.which")
    def test_validate_agent_valid(self, mock_which, mock_which_agent, factory):
        """Test validating a valid agent."""
        mock_which_agent.return_value = "/usr/local/bin/claude"
        mock_which.side_effect = lambda cmd: {
            "claude": "/usr/local/bin/claude",
            "git": "/usr/bin/git",
            "gh": "/usr/local/bin/gh",
        }.get(cmd)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)

            is_valid, message = factory.validate_agent("claude-code")

            assert is_valid is True
            assert "properly configured" in message

    @patch("cocode.agents.factory.which_agent")
    @patch("cocode.agents.factory.shutil.which")
    def test_validate_agent_invalid(self, mock_which, mock_which_agent, factory):
        """Test validating an invalid agent."""
        mock_which_agent.return_value = None
        mock_which.side_effect = lambda cmd: {
            "git": "/usr/bin/git",
            "gh": "/usr/local/bin/gh",
        }.get(cmd)

        is_valid, message = factory.validate_agent("claude-code")

        assert is_valid is False
        assert "not found on PATH" in message

    @patch("cocode.agents.factory.which_agent")
    @patch("cocode.agents.factory.shutil.which")
    def test_list_available_agents(self, mock_which, mock_which_agent, factory):
        """Test listing available agents."""
        mock_which_agent.side_effect = ["/usr/local/bin/claude", None]
        mock_which.side_effect = lambda cmd: {
            "claude": "/usr/local/bin/claude",
            "git": "/usr/bin/git",
            "gh": "/usr/local/bin/gh",
        }.get(cmd)

        factory.config_manager.list_agents.return_value = [
            {"name": "custom-agent", "command": "custom-agent"}
        ]

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)

            available = factory.list_available_agents()

            # Should have claude-code (valid), codex-cli (invalid), and custom-agent
            assert len(available) >= 2
            claude_info = next(a for a in available if a["name"] == "claude-code")
            assert claude_info["available"] is True
            assert claude_info["type"] == "built-in"

            codex_info = next(a for a in available if a["name"] == "codex-cli")
            assert codex_info["available"] is False
            assert codex_info["type"] == "built-in"

    def test_register_agent_type(self, factory):
        """Test registering a new agent type."""
        from cocode.agents.base import AgentConfig

        class CustomAgent(Agent):
            def __init__(self, config=None):
                if config is None:
                    config = AgentConfig(name="custom")
                super().__init__("custom", config)

            def run(self, *args, **kwargs):
                pass

            def check_ready(self, *args, **kwargs):
                return False

            def get_command(self):
                return ["custom"]

            def prepare_environment(self, *args, **kwargs):
                return {}

            def validate_environment(self, env=None):
                return True

        factory.register_agent_type("custom", CustomAgent)

        assert "custom" in factory._agent_registry
        assert factory._agent_registry["custom"] is CustomAgent

        # Should be able to create the registered agent
        with patch("cocode.agents.factory.AgentFactory._validate_dependencies"):
            agent = factory.create_agent("custom")
            assert isinstance(agent, CustomAgent)

    @patch("subprocess.run")
    @patch("cocode.agents.factory.shutil.which")
    @patch("cocode.agents.factory.which_agent")
    def test_validate_claude_code_version_check(
        self, mock_which_agent, mock_which, mock_run, factory
    ):
        """Test Claude Code version checking during validation."""
        mock_which_agent.return_value = "/usr/local/bin/claude"
        mock_which.side_effect = lambda cmd: {
            "claude": "/usr/local/bin/claude",
            "git": "/usr/bin/git",
            "gh": "/usr/local/bin/gh",
        }.get(cmd)

        # Track all subprocess calls
        mock_run.side_effect = [
            Mock(returncode=0, stdout="Claude CLI v1.2.3"),  # claude --version
            Mock(returncode=0),  # gh auth status
        ]

        is_valid, message = factory.validate_agent("claude-code")

        assert is_valid is True
        # Verify both commands were called
        assert len(mock_run.call_args_list) == 2
        assert mock_run.call_args_list[0][0][0] == ["claude", "--version"]
        assert mock_run.call_args_list[1][0][0] == ["gh", "auth", "status"]

    @patch("subprocess.run")
    @patch("cocode.agents.factory.shutil.which")
    @patch("cocode.agents.factory.which_agent")
    def test_validate_codex_cli_version_check(
        self, mock_which_agent, mock_which, mock_run, factory
    ):
        """Test Codex CLI version checking during validation."""
        mock_which_agent.return_value = "/usr/local/bin/codex"
        mock_which.side_effect = lambda cmd: {
            "codex": "/usr/local/bin/codex",
            "git": "/usr/bin/git",
            "gh": "/usr/local/bin/gh",
        }.get(cmd)

        # Track all subprocess calls
        mock_run.side_effect = [
            Mock(returncode=0, stdout="Codex CLI v2.0.0"),  # codex --version
            Mock(returncode=0),  # gh auth status
        ]

        is_valid, message = factory.validate_agent("codex-cli")

        assert is_valid is True
        # Verify both commands were called
        assert len(mock_run.call_args_list) == 2
        assert mock_run.call_args_list[0][0][0] == ["codex", "--version"]
        assert mock_run.call_args_list[1][0][0] == ["gh", "auth", "status"]

    @patch("subprocess.run")
    @patch("cocode.agents.factory.shutil.which")
    def test_validate_timeout_handling(self, mock_which, mock_run, factory):
        """Test handling of subprocess timeout during validation."""
        mock_which.side_effect = lambda cmd: {
            "claude": "/usr/local/bin/claude",
            "git": "/usr/bin/git",
            "gh": "/usr/local/bin/gh",
        }.get(cmd)

        mock_run.side_effect = subprocess.TimeoutExpired("gh", 5)

        with pytest.raises(DependencyError) as exc_info:
            factory.create_agent("claude-code")

        assert "auth check timed out" in str(exc_info.value)

    @patch("cocode.agents.factory.shutil.which")
    def test_custom_agent_command_validation(self, mock_which, factory):
        """Test validation of custom agent command from config."""
        mock_which.side_effect = lambda cmd: {
            "git": "/usr/bin/git",
            "gh": "/usr/local/bin/gh",
        }.get(cmd)

        factory.config_manager.get_agent.return_value = {
            "name": "my-agent",
            "command": "my-agent-cli",
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)

            with pytest.raises(DependencyError) as exc_info:
                factory.create_agent("my-agent")

            assert "my-agent-cli" in str(exc_info.value)
            assert "not found on PATH" in str(exc_info.value)
