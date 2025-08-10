"""Base agent interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class AgentStatus:
    """Status of an agent execution."""

    name: str
    branch: str
    worktree: Path
    ready: bool = False
    last_commit: str | None = None
    exit_code: int | None = None
    error_message: str | None = None


@dataclass
class AgentConfig:
    """Configuration for an agent."""

    name: str
    command: str | None = None
    args: list[str] | None = None
    timeout: int = 900  # Default 15 minutes
    environment: dict[str, str] | None = None
    custom_settings: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentConfig":
        """Create AgentConfig from dictionary."""
        return cls(
            name=data.get("name", ""),
            command=data.get("command"),
            args=data.get("args", []),
            timeout=data.get("timeout", 900),
            environment=data.get("environment", {}),
            custom_settings=data.get("custom_settings", {}),
        )


class Agent(ABC):
    """Base class for all code agents."""

    def __init__(self, name: str, config: AgentConfig | None = None):
        """Initialize agent with a name and optional configuration.

        Args:
            name: Agent name
            config: Optional agent configuration
        """
        self.name = name
        self.config = config or AgentConfig(name=name)

    @abstractmethod
    def validate_environment(self) -> bool:
        """Check if agent can run in current environment."""
        raise NotImplementedError

    @abstractmethod
    def prepare_environment(
        self, worktree_path: Path, issue_number: int, issue_body: str
    ) -> dict[str, str]:
        """Prepare environment variables for agent execution."""
        raise NotImplementedError

    @abstractmethod
    def get_command(self) -> list[str]:
        """Get the command to execute the agent."""
        raise NotImplementedError

    @abstractmethod
    def check_ready(self, worktree_path: Path) -> bool:
        """Check if agent has signaled it's ready."""
        raise NotImplementedError
