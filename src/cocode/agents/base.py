"""Base agent interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


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


class Agent(ABC):
    """Base class for all code agents."""

    def __init__(self, name: str):
        """Initialize agent with a name."""
        self.name = name

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
