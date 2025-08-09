"""Tests for ConfigManager."""

import json
from pathlib import Path

import pytest

from cocode.config.manager import (
    CONFIG_VERSION,
    DEFAULT_CONFIG,
    ConfigManager,
    ConfigurationError,
)


class TestConfigManager:
    """Test ConfigManager functionality."""

    def test_init_default_path(self):
        """Test initialization with default path."""
        manager = ConfigManager()
        assert manager.config_path == Path(".cocode/config.json")

    def test_init_custom_path(self, tmp_path):
        """Test initialization with custom path."""
        custom_path = tmp_path / "custom" / "config.json"
        manager = ConfigManager(custom_path)
        assert manager.config_path == custom_path

    def test_load_default_when_no_file(self, tmp_path):
        """Test loading defaults when config file doesn't exist."""
        config_path = tmp_path / "nonexistent" / "config.json"
        manager = ConfigManager(config_path)

        config = manager.load()

        assert config == DEFAULT_CONFIG
        assert config["version"] == CONFIG_VERSION
        assert config["agents"] == []
        assert config["base_agent"] is None

    def test_load_existing_config(self, tmp_path):
        """Test loading existing configuration file."""
        config_path = tmp_path / "config.json"
        test_config = {
            "version": "1.0.0",
            "agents": [{"name": "test-agent", "command": "test"}],
            "base_agent": "test-agent",
        }

        with open(config_path, "w") as f:
            json.dump(test_config, f)

        manager = ConfigManager(config_path)
        config = manager.load()

        assert config["agents"] == test_config["agents"]
        assert config["base_agent"] == "test-agent"
        # Check that defaults are merged in
        assert "performance" in config
        assert config["performance"]["max_concurrent_agents"] == 5

    def test_load_invalid_json(self, tmp_path):
        """Test loading invalid JSON raises error."""
        config_path = tmp_path / "config.json"

        with open(config_path, "w") as f:
            f.write("{ invalid json }")

        manager = ConfigManager(config_path)

        with pytest.raises(ConfigurationError, match="Invalid JSON"):
            manager.load()

    def test_save_config(self, tmp_path):
        """Test saving configuration."""
        config_path = tmp_path / "config.json"
        manager = ConfigManager(config_path)

        test_config = {
            "version": "1.0.0",
            "agents": [{"name": "agent1", "command": "cmd1"}],
            "base_agent": "agent1",
        }

        manager.save(test_config)

        assert config_path.exists()

        with open(config_path) as f:
            saved = json.load(f)

        assert saved["agents"] == test_config["agents"]
        assert saved["base_agent"] == "agent1"

    def test_save_creates_parent_dirs(self, tmp_path):
        """Test save creates parent directories if needed."""
        config_path = tmp_path / "nested" / "dirs" / "config.json"
        manager = ConfigManager(config_path)

        manager.save()

        assert config_path.exists()
        assert config_path.parent.exists()

    def test_get_value(self, tmp_path):
        """Test getting configuration values."""
        config_path = tmp_path / "config.json"
        manager = ConfigManager(config_path)

        test_config = {
            "version": "1.0.0",
            "performance": {
                "max_concurrent_agents": 3,
                "profile": "low",
            },
        }

        manager.save(test_config)

        assert manager.get("version") == "1.0.0"
        assert manager.get("performance.max_concurrent_agents") == 3
        assert manager.get("performance.profile") == "low"
        assert manager.get("nonexistent", "default") == "default"

    def test_set_value(self, tmp_path):
        """Test setting configuration values."""
        config_path = tmp_path / "config.json"
        manager = ConfigManager(config_path)

        manager.load()
        manager.set("performance.max_concurrent_agents", 10)
        manager.set("new.nested.value", "test")

        assert manager.get("performance.max_concurrent_agents") == 10
        assert manager.get("new.nested.value") == "test"

    def test_add_agent(self, tmp_path):
        """Test adding agent configuration."""
        config_path = tmp_path / "config.json"
        manager = ConfigManager(config_path)

        agent_config = {
            "name": "claude-code",
            "command": "claude-code",
            "args": ["--issue", "{issue_number}"],
        }

        manager.add_agent(agent_config)

        agents = manager.list_agents()
        assert len(agents) == 1
        assert agents[0]["name"] == "claude-code"

    def test_add_agent_missing_required_field(self, tmp_path):
        """Test adding agent without required fields raises error."""
        config_path = tmp_path / "config.json"
        manager = ConfigManager(config_path)

        agent_config = {"name": "incomplete-agent"}  # Missing 'command'

        with pytest.raises(ConfigurationError, match="missing required field: command"):
            manager.add_agent(agent_config)

    def test_add_duplicate_agent(self, tmp_path):
        """Test adding duplicate agent raises error."""
        config_path = tmp_path / "config.json"
        manager = ConfigManager(config_path)

        agent_config = {"name": "agent1", "command": "cmd1"}

        manager.add_agent(agent_config)

        with pytest.raises(ConfigurationError, match="already exists"):
            manager.add_agent(agent_config)

    def test_remove_agent(self, tmp_path):
        """Test removing agent configuration."""
        config_path = tmp_path / "config.json"
        manager = ConfigManager(config_path)

        agent1 = {"name": "agent1", "command": "cmd1"}
        agent2 = {"name": "agent2", "command": "cmd2"}

        manager.add_agent(agent1)
        manager.add_agent(agent2)

        assert len(manager.list_agents()) == 2

        removed = manager.remove_agent("agent1")
        assert removed is True
        assert len(manager.list_agents()) == 1
        assert manager.list_agents()[0]["name"] == "agent2"

        removed = manager.remove_agent("nonexistent")
        assert removed is False

    def test_remove_base_agent_clears_base(self, tmp_path):
        """Test removing base agent clears base_agent field."""
        config_path = tmp_path / "config.json"
        manager = ConfigManager(config_path)

        agent = {"name": "base", "command": "cmd"}
        manager.add_agent(agent)
        manager.set_base_agent("base")

        assert manager.get("base_agent") == "base"

        manager.remove_agent("base")

        assert manager.get("base_agent") is None

    def test_list_agents(self, tmp_path):
        """Test listing all agents."""
        config_path = tmp_path / "config.json"
        manager = ConfigManager(config_path)

        agents = [
            {"name": "agent1", "command": "cmd1"},
            {"name": "agent2", "command": "cmd2"},
            {"name": "agent3", "command": "cmd3"},
        ]

        for agent in agents:
            manager.add_agent(agent)

        listed = manager.list_agents()
        assert len(listed) == 3
        assert all(a["name"] in ["agent1", "agent2", "agent3"] for a in listed)

    def test_get_agent(self, tmp_path):
        """Test getting specific agent configuration."""
        config_path = tmp_path / "config.json"
        manager = ConfigManager(config_path)

        agent = {"name": "test-agent", "command": "test", "custom": "value"}
        manager.add_agent(agent)

        retrieved = manager.get_agent("test-agent")
        assert retrieved is not None
        assert retrieved["name"] == "test-agent"
        assert retrieved["custom"] == "value"

        assert manager.get_agent("nonexistent") is None

    def test_set_base_agent(self, tmp_path):
        """Test setting base agent."""
        config_path = tmp_path / "config.json"
        manager = ConfigManager(config_path)

        agent = {"name": "base-agent", "command": "cmd"}
        manager.add_agent(agent)

        manager.set_base_agent("base-agent")

        assert manager.get("base_agent") == "base-agent"

    def test_set_base_agent_not_found(self, tmp_path):
        """Test setting non-existent agent as base raises error."""
        config_path = tmp_path / "config.json"
        manager = ConfigManager(config_path)

        with pytest.raises(ConfigurationError, match="Agent 'nonexistent' not found"):
            manager.set_base_agent("nonexistent")

    def test_validate_invalid_config_type(self, tmp_path):
        """Test validation fails for non-dict config."""
        config_path = tmp_path / "config.json"
        manager = ConfigManager(config_path)

        with pytest.raises(ConfigurationError, match="must be a dictionary"):
            manager.save([])  # List instead of dict

    def test_validate_invalid_agents_type(self, tmp_path):
        """Test validation fails for invalid agents type."""
        config_path = tmp_path / "config.json"
        manager = ConfigManager(config_path)

        invalid_config = {"agents": "not-a-list"}

        with pytest.raises(ConfigurationError, match="Agents must be a list"):
            manager.save(invalid_config)

    def test_validate_invalid_performance_profile(self, tmp_path):
        """Test validation fails for invalid performance profile."""
        config_path = tmp_path / "config.json"
        manager = ConfigManager(config_path)

        invalid_config = {"performance": {"profile": "ultra-high"}}  # Invalid profile

        with pytest.raises(ConfigurationError, match="Performance profile must be"):
            manager.save(invalid_config)

    def test_validate_invalid_max_concurrent_agents(self, tmp_path):
        """Test validation fails for invalid max_concurrent_agents."""
        config_path = tmp_path / "config.json"
        manager = ConfigManager(config_path)

        invalid_config = {"performance": {"max_concurrent_agents": 0}}  # Must be positive

        with pytest.raises(ConfigurationError, match="must be a positive integer"):
            manager.save(invalid_config)

    def test_validate_invalid_timeout(self, tmp_path):
        """Test validation fails for invalid timeout."""
        config_path = tmp_path / "config.json"
        manager = ConfigManager(config_path)

        invalid_config = {"performance": {"agent_timeout": -10}}  # Must be positive

        with pytest.raises(ConfigurationError, match="must be a positive number"):
            manager.save(invalid_config)

    def test_merge_with_defaults(self, tmp_path):
        """Test config is properly merged with defaults."""
        config_path = tmp_path / "config.json"
        partial_config = {
            "agents": [{"name": "test", "command": "test"}],
            "performance": {
                "profile": "high"  # Only set profile, other fields should use defaults
            },
        }

        with open(config_path, "w") as f:
            json.dump(partial_config, f)

        manager = ConfigManager(config_path)
        config = manager.load()

        # Custom values preserved
        assert config["agents"][0]["name"] == "test"
        assert config["performance"]["profile"] == "high"

        # Defaults filled in
        assert config["version"] == CONFIG_VERSION
        assert config["performance"]["max_concurrent_agents"] == 5
        assert config["performance"]["agent_timeout"] == 900
        assert config["logging"]["level"] == "INFO"
        assert config["git"]["base_branch"] == "main"

    def test_reset_to_defaults(self, tmp_path):
        """Test resetting configuration to defaults."""
        config_path = tmp_path / "config.json"
        manager = ConfigManager(config_path)

        # Add some custom config
        manager.add_agent({"name": "test", "command": "test"})
        manager.set("performance.profile", "high")

        # Reset
        manager.reset_to_defaults()

        assert manager.get("agents") == []
        assert manager.get("performance.profile") == "medium"
        assert manager._config == DEFAULT_CONFIG


class TestConfigManagerIntegration:
    """Integration tests for ConfigManager."""

    def test_full_workflow(self, tmp_path):
        """Test complete configuration workflow."""
        config_path = tmp_path / ".cocode" / "config.json"
        manager = ConfigManager(config_path)

        # Initial load creates defaults
        config = manager.load()
        assert config["version"] == CONFIG_VERSION

        # Add multiple agents
        agents = [
            {
                "name": "claude-code",
                "command": "claude-code",
                "args": ["--issue", "{issue_number}"],
                "env": {"CLAUDE_API_KEY": "key"},
            },
            {
                "name": "codex",
                "command": "codex-cli",
                "args": ["fix", "--issue={issue_number}"],
            },
            {
                "name": "gpt-engineer",
                "command": "gpt-engineer",
                "args": ["--prompt", "{issue_body}"],
            },
        ]

        for agent in agents:
            manager.add_agent(agent)

        # Set base agent
        manager.set_base_agent("claude-code")

        # Configure performance
        manager.set("performance.max_concurrent_agents", 3)
        manager.set("performance.profile", "low")
        manager.set("performance.agent_timeout", 1800)

        # Configure logging
        manager.set("logging.level", "DEBUG")

        # Save configuration
        manager.save()

        # Load in new manager instance
        new_manager = ConfigManager(config_path)
        loaded_config = new_manager.load()

        # Verify all settings persisted
        assert len(loaded_config["agents"]) == 3
        assert loaded_config["base_agent"] == "claude-code"
        assert loaded_config["performance"]["max_concurrent_agents"] == 3
        assert loaded_config["performance"]["profile"] == "low"
        assert loaded_config["performance"]["agent_timeout"] == 1800
        assert loaded_config["logging"]["level"] == "DEBUG"

        # Verify agent retrieval
        claude = new_manager.get_agent("claude-code")
        assert claude is not None
        assert claude["env"]["CLAUDE_API_KEY"] == "key"

        # Remove an agent
        new_manager.remove_agent("gpt-engineer")
        assert len(new_manager.list_agents()) == 2

        # Save and verify removal persisted
        new_manager.save()

        final_manager = ConfigManager(config_path)
        final_config = final_manager.load()
        assert len(final_config["agents"]) == 2
        assert all(a["name"] != "gpt-engineer" for a in final_config["agents"])
