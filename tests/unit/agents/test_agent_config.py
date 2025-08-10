"""Tests for agent configuration passing."""

from __future__ import annotations

from unittest.mock import Mock, patch

from cocode.agents.base import AgentConfig
from cocode.agents.claude_code import ClaudeCodeAgent
from cocode.agents.codex_cli import CodexCliAgent
from cocode.agents.default import GitBasedAgent
from cocode.agents.factory import AgentFactory
from cocode.config.manager import ConfigManager


class TestAgentConfig:
    """Test AgentConfig class."""

    def test_agent_config_creation(self):
        """Test creating an AgentConfig."""
        config = AgentConfig(
            name="test-agent",
            command="test-cmd",
            args=["--flag", "value"],
            timeout=1800,
            environment={"KEY": "value"},
            custom_settings={"model": "gpt-4"},
        )

        assert config.name == "test-agent"
        assert config.command == "test-cmd"
        assert config.args == ["--flag", "value"]
        assert config.timeout == 1800
        assert config.environment == {"KEY": "value"}
        assert config.custom_settings == {"model": "gpt-4"}

    def test_agent_config_from_dict(self):
        """Test creating AgentConfig from dictionary."""
        data = {
            "name": "test-agent",
            "command": "test-cmd",
            "args": ["--flag"],
            "timeout": 600,
            "environment": {"API_KEY": "secret"},
            "custom_settings": {"temperature": 0.7},
        }

        config = AgentConfig.from_dict(data)

        assert config.name == "test-agent"
        assert config.command == "test-cmd"
        assert config.args == ["--flag"]
        assert config.timeout == 600
        assert config.environment == {"API_KEY": "secret"}
        assert config.custom_settings == {"temperature": 0.7}

    def test_agent_config_defaults(self):
        """Test AgentConfig with defaults."""
        config = AgentConfig(name="minimal")

        assert config.name == "minimal"
        assert config.command is None
        assert config.args is None
        assert config.timeout == 900
        assert config.environment is None
        assert config.custom_settings is None


class TestClaudeCodeAgentConfig:
    """Test ClaudeCodeAgent configuration support."""

    @patch("cocode.agents.claude_code.shutil.which")
    def test_claude_code_with_config(self, mock_which):
        """Test ClaudeCodeAgent uses configuration."""
        mock_which.return_value = "/usr/local/bin/custom-claude"

        config = AgentConfig(
            name="claude-code",
            command="custom-claude",
            args=["special", "--mode", "fast"],
            environment={"CLAUDE_MODEL": "claude-3-opus"},
        )

        agent = ClaudeCodeAgent(config)

        assert agent.name == "claude-code"
        assert agent.config.command == "custom-claude"
        assert agent.config.args == ["special", "--mode", "fast"]
        assert agent.config.environment == {"CLAUDE_MODEL": "claude-3-opus"}

        # Validate environment finds custom command
        assert agent.validate_environment() is True
        mock_which.assert_called_with("custom-claude")

    @patch("cocode.agents.claude_code.shutil.which")
    def test_claude_code_get_command_with_custom_args(self, mock_which):
        """Test ClaudeCodeAgent uses custom args from config."""
        mock_which.return_value = "/usr/local/bin/claude"

        config = AgentConfig(
            name="claude-code",
            command="claude",
            args=["custom", "command", "--no-cache"],
        )

        agent = ClaudeCodeAgent(config)
        agent.validate_environment()

        command = agent.get_command()
        assert command == ["/usr/local/bin/claude", "custom", "command", "--no-cache"]

    def test_claude_code_prepare_environment_with_config(self):
        """Test ClaudeCodeAgent passes through custom environment variables."""
        config = AgentConfig(
            name="claude-code",
            environment={"CLAUDE_API_KEY": "sk-test", "CLAUDE_MODEL": "claude-3"},
        )

        agent = ClaudeCodeAgent(config)
        env = agent.prepare_environment(None, 123, "issue body")

        assert env == {"CLAUDE_API_KEY": "sk-test", "CLAUDE_MODEL": "claude-3"}


class TestCodexCliAgentConfig:
    """Test CodexCliAgent configuration support."""

    @patch("cocode.agents.codex_cli.subprocess.run")
    @patch("cocode.agents.codex_cli.shutil.which")
    def test_codex_cli_with_config(self, mock_which, mock_run):
        """Test CodexCliAgent uses configuration."""
        mock_which.return_value = "/opt/bin/codex-pro"
        mock_run.return_value = Mock(returncode=0, stdout="codex help output")

        config = AgentConfig(
            name="codex-cli",
            command="codex-pro",
            args=["turbo", "--parallel"],
            environment={"CODEX_MODEL": "gpt-4-turbo"},
        )

        agent = CodexCliAgent(config)

        assert agent.name == "codex-cli"
        assert agent.config.command == "codex-pro"
        assert agent.config.args == ["turbo", "--parallel"]

        # Validate environment finds custom command
        assert agent.validate_environment() is True
        mock_which.assert_called_with("codex-pro")

    @patch("cocode.agents.codex_cli.shutil.which")
    @patch("cocode.agents.codex_cli.subprocess.run")
    @patch("cocode.agents.codex_cli.os.environ")
    def test_codex_cli_custom_args_override(self, mock_environ, mock_run, mock_which):
        """Test CodexCliAgent custom args override default command building."""
        mock_which.return_value = "/usr/bin/codex"
        # Mock help output to indicate standard CLI style
        mock_run.return_value = Mock(returncode=0, stdout="fix --issue-file")
        mock_environ.get.return_value = None  # No env vars set

        config = AgentConfig(name="codex-cli", command="codex", args=["analyze", "--quick"])

        agent = CodexCliAgent(config)
        agent.validate_environment()

        command = agent.get_command()
        # Custom args should completely replace default command
        assert command == ["/usr/bin/codex", "analyze", "--quick"]


class TestGitBasedAgentConfig:
    """Test GitBasedAgent configuration support."""

    @patch("cocode.agents.default.shutil.which")
    def test_git_based_agent_with_command_config(self, mock_which):
        """Test GitBasedAgent validates and uses command from config."""
        mock_which.return_value = "/usr/local/bin/my-agent"

        config = AgentConfig(
            name="custom-agent",
            command="my-agent",
            args=["--issue-file", "issue.txt"],
            environment={"AGENT_TOKEN": "secret"},
        )

        agent = GitBasedAgent("custom-agent", config)

        # Validate checks for command
        assert agent.validate_environment() is True
        mock_which.assert_called_with("my-agent")

        # Get command uses config
        command = agent.get_command()
        assert command == ["my-agent", "--issue-file", "issue.txt"]

        # Environment variables passed through
        env = agent.prepare_environment(None, 123, "issue")
        assert env == {"AGENT_TOKEN": "secret"}

    @patch("cocode.agents.default.shutil.which")
    def test_git_based_agent_command_not_found(self, mock_which):
        """Test GitBasedAgent validation fails when command not found."""
        mock_which.return_value = None

        config = AgentConfig(name="missing-agent", command="nonexistent")

        agent = GitBasedAgent("missing-agent", config)

        assert agent.validate_environment() is False


class TestAgentFactoryConfig:
    """Test AgentFactory configuration passing."""

    @patch("cocode.agents.factory.which_agent")
    @patch("cocode.agents.factory.shutil.which")
    def test_factory_passes_config_to_claude_code(self, mock_which, mock_which_agent):
        """Test factory passes configuration to ClaudeCodeAgent."""
        mock_which_agent.return_value = "/usr/bin/claude"
        mock_which.return_value = "/usr/bin/claude"

        config_manager = Mock(spec=ConfigManager)
        config_manager.get_agent.return_value = {
            "name": "claude-code",
            "command": "claude",
            "args": ["code", "--fast"],
            "timeout": 600,
            "environment": {"CLAUDE_API_KEY": "test-key"},
        }

        factory = AgentFactory(config_manager)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            agent = factory.create_agent("claude-code")

        assert isinstance(agent, ClaudeCodeAgent)
        assert agent.config.command == "claude"
        assert agent.config.args == ["code", "--fast"]
        assert agent.config.timeout == 600
        assert agent.config.environment == {"CLAUDE_API_KEY": "test-key"}

    @patch("cocode.agents.factory.which_agent")
    @patch("cocode.agents.factory.shutil.which")
    def test_factory_config_override(self, mock_which, mock_which_agent):
        """Test factory config override functionality."""
        mock_which_agent.return_value = "/usr/bin/claude"
        mock_which.return_value = "/usr/bin/claude"

        config_manager = Mock(spec=ConfigManager)
        config_manager.get_agent.return_value = {
            "name": "claude-code",
            "timeout": 900,
        }

        factory = AgentFactory(config_manager)

        override = {
            "timeout": 1800,
            "args": ["--experimental"],
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            agent = factory.create_agent("claude-code", config_override=override)

        assert agent.config.timeout == 1800
        assert agent.config.args == ["--experimental"]

    @patch("cocode.agents.factory.shutil.which")
    def test_factory_creates_custom_agent_from_config(self, mock_which):
        """Test factory creates custom agent from configuration only."""
        mock_which.side_effect = lambda cmd: {
            "git": "/usr/bin/git",
            "gh": "/usr/bin/gh",
            "my-custom-agent": "/opt/agents/my-custom-agent",
        }.get(cmd)

        config_manager = Mock(spec=ConfigManager)
        config_manager.get_agent.return_value = {
            "name": "my-custom-agent",
            "command": "my-custom-agent",
            "args": ["solve", "--auto"],
            "environment": {"CUSTOM_KEY": "value"},
        }

        factory = AgentFactory(config_manager)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            agent = factory.create_agent("my-custom-agent")

        # Should create GitBasedAgent for unknown agent types
        assert isinstance(agent, GitBasedAgent)
        assert agent.name == "my-custom-agent"
        assert agent.config.command == "my-custom-agent"
        assert agent.config.args == ["solve", "--auto"]
        assert agent.config.environment == {"CUSTOM_KEY": "value"}

        # Verify it can generate correct command
        command = agent.get_command()
        assert command == ["my-custom-agent", "solve", "--auto"]
