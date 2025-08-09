"""Configuration file management."""

import copy
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Configuration schema version
CONFIG_VERSION = "1.0.0"

# Default configuration schema
DEFAULT_CONFIG = {
    "version": CONFIG_VERSION,
    "agents": [],
    "base_agent": None,
    "performance": {
        "max_concurrent_agents": 5,
        "agent_timeout": 900,  # 15 minutes in seconds
        "profile": "medium",  # low, medium, high
    },
    "logging": {
        "level": "INFO",
        "max_log_size_mb": 10,
    },
    "git": {
        "base_branch": "main",
        "fetch_before_run": True,
    },
}


class ConfigurationError(Exception):
    """Configuration related errors."""

    pass


class ConfigManager:
    """Manages cocode configuration."""

    def __init__(self, config_path: Path | None = None):
        """Initialize config manager.

        Args:
            config_path: Path to configuration file. Defaults to .cocode/config.json
        """
        self.config_path = config_path or Path(".cocode/config.json")
        self._config: dict[str, Any] = {}

    def load(self) -> dict[str, Any]:
        """Load configuration from file.

        Returns:
            Configuration dictionary

        Raises:
            ConfigurationError: If config file is invalid
        """
        if not self.config_path.exists():
            logger.debug(f"Config file {self.config_path} not found, using defaults")
            # Deep copy to avoid modifying the DEFAULT_CONFIG
            self._config = copy.deepcopy(DEFAULT_CONFIG)
            return self._config

        try:
            with open(self.config_path) as f:
                self._config = json.load(f)

            # Validate and merge with defaults
            self._validate_config()
            self._merge_with_defaults()

            logger.debug(f"Loaded configuration from {self.config_path}")
            return self._config

        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Invalid JSON in config file: {e}") from e
        except Exception as e:
            raise ConfigurationError(f"Failed to load config: {e}") from e

    def save(self, config: dict[str, Any] | None = None) -> None:
        """Save configuration to file.

        Args:
            config: Configuration to save. If None, saves current config.

        Raises:
            ConfigurationError: If save fails
        """
        if config is not None:
            self._config = config
            self._validate_config()

        if not self._config:
            self._config = copy.deepcopy(DEFAULT_CONFIG)

        # Ensure parent directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(self.config_path, "w") as f:
                json.dump(self._config, f, indent=2)
            logger.debug(f"Saved configuration to {self.config_path}")
        except Exception as e:
            raise ConfigurationError(f"Failed to save config: {e}") from e

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key.

        Args:
            key: Configuration key (supports dot notation)
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        if not self._config:
            self.load()

        # Support dot notation (e.g., "performance.max_concurrent_agents")
        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """Set configuration value.

        Args:
            key: Configuration key (supports dot notation)
            value: Value to set
        """
        if not self._config:
            self.load()

        # Support dot notation
        keys = key.split(".")
        target = self._config

        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]

        target[keys[-1]] = value

    def add_agent(self, agent_config: dict[str, Any]) -> None:
        """Add an agent configuration.

        Args:
            agent_config: Agent configuration dictionary

        Raises:
            ConfigurationError: If agent config is invalid
        """
        if not self._config:
            self.load()

        # Validate agent config
        required_fields = ["name", "command"]
        for field in required_fields:
            if field not in agent_config:
                raise ConfigurationError(f"Agent config missing required field: {field}")

        # Check for duplicate names
        existing_names = [a["name"] for a in self._config.get("agents", [])]
        if agent_config["name"] in existing_names:
            raise ConfigurationError(f"Agent with name '{agent_config['name']}' already exists")

        if "agents" not in self._config:
            self._config["agents"] = []

        self._config["agents"].append(agent_config)

    def remove_agent(self, agent_name: str) -> bool:
        """Remove an agent configuration.

        Args:
            agent_name: Name of agent to remove

        Returns:
            True if agent was removed, False if not found
        """
        if not self._config:
            self.load()

        agents = self._config.get("agents", [])
        original_count = len(agents)

        self._config["agents"] = [a for a in agents if a.get("name") != agent_name]

        # If this was the base agent, clear it
        if self._config.get("base_agent") == agent_name:
            self._config["base_agent"] = None

        return len(self._config["agents"]) < original_count

    def list_agents(self) -> list[dict[str, Any]]:
        """List all configured agents.

        Returns:
            List of agent configurations
        """
        if not self._config:
            self.load()

        agents: list[dict[str, Any]] = self._config.get("agents", [])
        return agents

    def get_agent(self, agent_name: str) -> dict[str, Any] | None:
        """Get specific agent configuration.

        Args:
            agent_name: Name of agent

        Returns:
            Agent configuration or None if not found
        """
        agents = self.list_agents()
        for agent in agents:
            if agent.get("name") == agent_name:
                return agent
        return None

    def set_base_agent(self, agent_name: str) -> None:
        """Set the base agent for comparisons.

        Args:
            agent_name: Name of agent to use as base

        Raises:
            ConfigurationError: If agent not found
        """
        if not self.get_agent(agent_name):
            raise ConfigurationError(f"Agent '{agent_name}' not found")

        self._config["base_agent"] = agent_name

    def _validate_config(self) -> None:
        """Validate configuration structure.

        Raises:
            ConfigurationError: If config is invalid
        """
        if not isinstance(self._config, dict):
            raise ConfigurationError("Configuration must be a dictionary")

        # Validate version if present
        if "version" in self._config:
            version = self._config["version"]
            if not isinstance(version, str):
                raise ConfigurationError("Configuration version must be a string")

        # Validate agents
        if "agents" in self._config:
            agents = self._config["agents"]
            if not isinstance(agents, list):
                raise ConfigurationError("Agents must be a list")

            for i, agent in enumerate(agents):
                if not isinstance(agent, dict):
                    raise ConfigurationError(f"Agent {i} must be a dictionary")
                if "name" not in agent:
                    raise ConfigurationError(f"Agent {i} missing 'name' field")
                if "command" not in agent:
                    raise ConfigurationError(f"Agent {i} missing 'command' field")

        # Validate performance settings
        if "performance" in self._config:
            perf = self._config["performance"]
            if not isinstance(perf, dict):
                raise ConfigurationError("Performance settings must be a dictionary")

            if "profile" in perf and perf["profile"] not in ["low", "medium", "high"]:
                raise ConfigurationError("Performance profile must be 'low', 'medium', or 'high'")

            if "max_concurrent_agents" in perf:
                max_agents = perf["max_concurrent_agents"]
                if not isinstance(max_agents, int) or max_agents < 1:
                    raise ConfigurationError("max_concurrent_agents must be a positive integer")

            if "agent_timeout" in perf:
                timeout = perf["agent_timeout"]
                if not isinstance(timeout, int | float) or timeout <= 0:
                    raise ConfigurationError("agent_timeout must be a positive number")

    def _merge_with_defaults(self) -> None:
        """Merge loaded config with defaults for missing fields."""

        def deep_merge(default: dict, config: dict) -> dict:
            """Recursively merge config with defaults."""
            result = copy.deepcopy(default)
            for key, value in config.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = deep_merge(result[key], value)
                else:
                    result[key] = value
            return result

        self._config = deep_merge(DEFAULT_CONFIG, self._config)

    def reset_to_defaults(self) -> None:
        """Reset configuration to defaults."""
        self._config = copy.deepcopy(DEFAULT_CONFIG)
        logger.info("Configuration reset to defaults")
