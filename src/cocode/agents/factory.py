"""Agent factory for creating and configuring agents.

This module provides the AgentFactory class which handles:
- Agent instantiation based on type
- Configuration mapping from config files
- Dependency validation for each agent type
- Comprehensive error handling with actionable messages
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from typing import Any, cast

from cocode.agents.base import Agent
from cocode.agents.claude_code import ClaudeCodeAgent
from cocode.agents.codex_cli import CodexCliAgent
from cocode.agents.default import GitBasedAgent
from cocode.agents.discovery import which_agent
from cocode.config.manager import ConfigManager

logger = logging.getLogger(__name__)


class AgentFactoryError(Exception):
    """Agent factory related errors."""

    pass


class DependencyError(AgentFactoryError):
    """Agent dependency validation errors."""

    pass


class AgentFactory:
    """Factory for creating and configuring agents.

    Handles agent instantiation, configuration mapping, and dependency validation
    following the architecture defined in ADR-003.
    """

    def __init__(self, config_manager: ConfigManager | None = None):
        """Initialize the agent factory.

        Args:
            config_manager: Optional config manager instance. If not provided,
                           a new instance will be created.
        """
        self.config_manager = config_manager or ConfigManager()
        # Use Any for the agent classes since they have different signatures
        self._agent_registry: dict[str, Any] = {
            "claude-code": ClaudeCodeAgent,
            "codex-cli": CodexCliAgent,
        }

    def create_agent(
        self,
        agent_name: str,
        config_override: dict[str, Any] | None = None,
        validate_dependencies: bool = True,
    ) -> Agent:
        """Create an agent instance with configuration.

        Args:
            agent_name: Name of the agent to create
            config_override: Optional configuration overrides
            validate_dependencies: Whether to validate agent dependencies

        Returns:
            Configured agent instance

        Raises:
            AgentFactoryError: If agent creation fails
            DependencyError: If dependency validation fails
        """
        try:
            # Get agent configuration from config manager
            agent_config = self._get_agent_config(agent_name, config_override)

            # Validate dependencies if requested
            if validate_dependencies:
                self._validate_dependencies(agent_name, agent_config)

            # Create agent instance
            agent = self._instantiate_agent(agent_name, agent_config)

            logger.info(f"Successfully created agent: {agent_name}")
            return agent

        except DependencyError:
            raise
        except Exception as e:
            raise AgentFactoryError(f"Failed to create agent '{agent_name}': {e}") from e

    def create_agents(
        self,
        agent_names: list[str] | None = None,
        validate_dependencies: bool = True,
    ) -> dict[str, Agent]:
        """Create multiple agents.

        Args:
            agent_names: List of agent names to create. If None, creates all configured agents.
            validate_dependencies: Whether to validate dependencies

        Returns:
            Dictionary mapping agent names to instances

        Raises:
            AgentFactoryError: If any agent creation fails
        """
        # If no specific agents requested, get all configured agents
        if agent_names is None:
            configured_agents = self.config_manager.list_agents()
            agent_names = [agent["name"] for agent in configured_agents]

        agents = {}
        errors = []

        for name in agent_names:
            try:
                agents[name] = self.create_agent(name, validate_dependencies=validate_dependencies)
            except Exception as e:
                errors.append(f"{name}: {e}")
                logger.error(f"Failed to create agent {name}: {e}")

        if errors:
            error_msg = "Failed to create some agents:\n" + "\n".join(errors)
            raise AgentFactoryError(error_msg)

        return agents

    def validate_agent(self, agent_name: str) -> tuple[bool, str]:
        """Validate an agent's dependencies without creating it.

        Args:
            agent_name: Name of agent to validate

        Returns:
            Tuple of (is_valid, message)
        """
        try:
            config = self._get_agent_config(agent_name)
            self._validate_dependencies(agent_name, config)
            return True, f"Agent '{agent_name}' is properly configured and all dependencies are met"
        except DependencyError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Validation failed: {e}"

    def list_available_agents(self) -> list[dict[str, Any]]:
        """List all available agents with their status.

        Returns:
            List of agent info dictionaries with name, configured, and available status
        """
        available = []

        # Check registered agent types
        for agent_name in self._agent_registry:
            is_valid, message = self.validate_agent(agent_name)
            available.append(
                {
                    "name": agent_name,
                    "type": "built-in",
                    "available": is_valid,
                    "message": message,
                }
            )

        # Check configured custom agents
        configured_agents = self.config_manager.list_agents()
        for agent_config in configured_agents:
            name = agent_config["name"]
            if name not in self._agent_registry:
                is_valid, message = self.validate_agent(name)
                available.append(
                    {
                        "name": name,
                        "type": "custom",
                        "available": is_valid,
                        "message": message,
                    }
                )

        return available

    def _get_agent_config(
        self, agent_name: str, config_override: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Get agent configuration.

        Args:
            agent_name: Name of agent
            config_override: Optional configuration overrides

        Returns:
            Agent configuration dictionary
        """
        # Start with config from manager
        base_config = self.config_manager.get_agent(agent_name) or {}

        # For known agents, provide defaults
        if agent_name in self._agent_registry:
            if not base_config:
                base_config = {"name": agent_name}

        # Apply overrides
        if config_override:
            base_config.update(config_override)

        return base_config

    def _instantiate_agent(self, agent_name: str, config: dict[str, Any]) -> Agent:
        """Instantiate an agent with configuration.

        Args:
            agent_name: Name of agent
            config: Agent configuration

        Returns:
            Agent instance
        """
        from cocode.agents.base import AgentConfig

        # Create AgentConfig from dictionary
        agent_config = AgentConfig.from_dict(config)

        # Check if it's a registered agent type
        if agent_name in self._agent_registry:
            agent_class = self._agent_registry[agent_name]
            return cast(Agent, agent_class(agent_config))

        # Otherwise, create a generic git-based agent
        # This allows for custom agents defined only in configuration
        return GitBasedAgent(agent_name, agent_config)

    def _validate_dependencies(self, agent_name: str, config: dict[str, Any]) -> None:
        """Validate agent dependencies.

        Args:
            agent_name: Name of agent
            config: Agent configuration

        Raises:
            DependencyError: If dependencies are not met
        """
        errors = []

        # Check if agent binary is available on PATH
        agent_path = which_agent(agent_name)
        if not agent_path:
            # For custom agents, check the command from config
            if "command" in config:
                command = config["command"]
                if not shutil.which(command):
                    errors.append(f"Command '{command}' not found on PATH")
            else:
                errors.append(f"Agent '{agent_name}' not found on PATH")

        # Agent-specific dependency checks
        if agent_name == "claude-code":
            self._validate_claude_code_dependencies(errors)
        elif agent_name == "codex-cli":
            self._validate_codex_cli_dependencies(errors)

        # Check git is available (required for all agents)
        if not shutil.which("git"):
            errors.append("Git is not installed or not on PATH")

        # Check gh CLI for GitHub operations
        if not shutil.which("gh"):
            errors.append("GitHub CLI (gh) is not installed. Install from: https://cli.github.com")
        else:
            # Check gh authentication
            try:
                result = subprocess.run(
                    ["gh", "auth", "status"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode != 0:
                    errors.append("GitHub CLI not authenticated. Run: gh auth login")
            except subprocess.TimeoutExpired:
                errors.append("GitHub CLI auth check timed out")
            except Exception as e:
                errors.append(f"Failed to check GitHub CLI auth: {e}")

        if errors:
            raise DependencyError(
                f"Dependency validation failed for '{agent_name}':\n"
                + "\n".join(f"  - {error}" for error in errors)
            )

    def _validate_claude_code_dependencies(self, errors: list[str]) -> None:
        """Validate Claude Code specific dependencies.

        Args:
            errors: List to append errors to
        """
        # Check for Claude CLI
        if not shutil.which("claude"):
            errors.append(
                "Claude CLI not found. Ensure 'claude' command is available on PATH. "
                "Install Claude Code from: https://claude.ai/download"
            )
            return

        # Check Claude CLI version if possible
        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                errors.append("Failed to get Claude CLI version")
            else:
                logger.debug(f"Claude CLI version: {result.stdout.strip()}")
        except subprocess.TimeoutExpired:
            errors.append("Claude CLI version check timed out")
        except Exception as e:
            logger.warning(f"Could not check Claude CLI version: {e}")

    def _validate_codex_cli_dependencies(self, errors: list[str]) -> None:
        """Validate Codex CLI specific dependencies.

        Args:
            errors: List to append errors to
        """
        # Check for Codex CLI
        if not shutil.which("codex"):
            errors.append(
                "Codex CLI not found. Ensure 'codex' command is available on PATH. "
                "Install Codex from your organization's deployment guide."
            )
            return

        # Check Codex CLI version if possible
        try:
            result = subprocess.run(
                ["codex", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                errors.append("Failed to get Codex CLI version")
            else:
                logger.debug(f"Codex CLI version: {result.stdout.strip()}")
        except subprocess.TimeoutExpired:
            errors.append("Codex CLI version check timed out")
        except Exception as e:
            logger.warning(f"Could not check Codex CLI version: {e}")

    def register_agent_type(self, name: str, agent_class: Any) -> None:
        """Register a new agent type.

        Args:
            name: Name for the agent type
            agent_class: Agent class to register
        """
        self._agent_registry[name] = agent_class
        logger.info(f"Registered agent type: {name}")
