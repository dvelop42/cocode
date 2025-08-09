"""State management with persistence and recovery."""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# State schema version
STATE_VERSION = "1.0.0"


class StateError(Exception):
    """State management related errors."""

    pass


@dataclass
class AgentState:
    """State for a single agent execution."""

    name: str
    branch: str
    worktree: str
    status: str  # pending, running, ready, failed, cancelled
    started_at: str | None = None
    completed_at: str | None = None
    exit_code: int | None = None
    last_commit: str | None = None
    error_message: str | None = None


@dataclass
class RunState:
    """State for a complete cocode run."""

    issue_number: int
    issue_url: str
    base_branch: str
    agents: list[AgentState] = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: str | None = None
    selected_agent: str | None = None
    pr_url: str | None = None


class StateManager:
    """Manages cocode execution state with persistence and recovery."""

    def __init__(self, state_path: Path | None = None):
        """Initialize state manager.

        Args:
            state_path: Path to state file. Defaults to .cocode/state.json
        """
        self.state_path = state_path or Path(".cocode/state.json")
        self._current_run: RunState | None = None

    def start_run(self, issue_number: int, issue_url: str, base_branch: str = "main") -> RunState:
        """Start a new run and persist initial state.

        Args:
            issue_number: GitHub issue number
            issue_url: Full URL to the issue
            base_branch: Base branch for the run

        Returns:
            New RunState instance

        Raises:
            StateError: If there's an active run
        """
        if self._current_run and not self._current_run.completed_at:
            raise StateError("There's already an active run. Complete or abort it first.")

        self._current_run = RunState(
            issue_number=issue_number,
            issue_url=issue_url,
            base_branch=base_branch,
        )

        self._persist()
        logger.info(f"Started run for issue #{issue_number}")
        return self._current_run

    def add_agent(self, name: str, branch: str, worktree: str) -> AgentState:
        """Add an agent to the current run.

        Args:
            name: Agent name
            branch: Git branch for this agent
            worktree: Path to agent's worktree

        Returns:
            New AgentState instance

        Raises:
            StateError: If no active run
        """
        if not self._current_run:
            raise StateError("No active run. Call start_run first.")

        # Check for duplicate agent names
        if any(a.name == name for a in self._current_run.agents):
            raise StateError(f"Agent '{name}' already exists in this run")

        agent = AgentState(
            name=name,
            branch=branch,
            worktree=worktree,
            status="pending",
        )

        self._current_run.agents.append(agent)
        self._persist()
        logger.debug(f"Added agent '{name}' to run")
        return agent

    def update_agent(
        self,
        name: str,
        status: str | None = None,
        exit_code: int | None = None,
        last_commit: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Update agent state.

        Args:
            name: Agent name
            status: New status
            exit_code: Process exit code
            last_commit: Latest commit SHA
            error_message: Error message if failed

        Raises:
            StateError: If agent not found
        """
        if not self._current_run:
            raise StateError("No active run")

        agent = self.get_agent(name)
        if not agent:
            raise StateError(f"Agent '{name}' not found")

        if status:
            agent.status = status
            if status == "running" and not agent.started_at:
                agent.started_at = datetime.now().isoformat()
            elif status in ["ready", "failed", "cancelled"] and not agent.completed_at:
                agent.completed_at = datetime.now().isoformat()

        if exit_code is not None:
            agent.exit_code = exit_code

        if last_commit:
            agent.last_commit = last_commit

        if error_message:
            agent.error_message = error_message

        self._persist()
        logger.debug(f"Updated agent '{name}' status to '{status}'")

    def get_agent(self, name: str) -> AgentState | None:
        """Get agent state by name.

        Args:
            name: Agent name

        Returns:
            AgentState or None if not found
        """
        if not self._current_run:
            return None

        for agent in self._current_run.agents:
            if agent.name == name:
                return agent
        return None

    def complete_run(self, selected_agent: str | None = None, pr_url: str | None = None) -> None:
        """Complete the current run.

        Args:
            selected_agent: Name of agent selected for PR
            pr_url: URL of created PR

        Raises:
            StateError: If no active run
        """
        if not self._current_run:
            raise StateError("No active run to complete")

        self._current_run.completed_at = datetime.now().isoformat()
        self._current_run.selected_agent = selected_agent
        self._current_run.pr_url = pr_url

        self._persist()
        logger.info(f"Completed run for issue #{self._current_run.issue_number}")

    def abort_run(self) -> None:
        """Abort the current run and mark all pending agents as cancelled."""
        if not self._current_run:
            raise StateError("No active run to abort")

        # Mark all pending/running agents as cancelled
        for agent in self._current_run.agents:
            if agent.status in ["pending", "running"]:
                agent.status = "cancelled"
                if not agent.completed_at:
                    agent.completed_at = datetime.now().isoformat()

        self._current_run.completed_at = datetime.now().isoformat()
        self._persist()
        logger.info(f"Aborted run for issue #{self._current_run.issue_number}")

    def load(self) -> RunState | None:
        """Load state from disk.

        Returns:
            Loaded RunState or None if no state file

        Raises:
            StateError: If state file is corrupted
        """
        if not self.state_path.exists():
            logger.debug(f"No state file at {self.state_path}")
            return None

        try:
            with open(self.state_path) as f:
                data = json.load(f)

            # Reconstruct dataclasses from JSON
            run_data = data.get("run")
            if not run_data:
                return None

            # Convert agent dicts to AgentState objects
            agents = [AgentState(**agent) for agent in run_data.get("agents", [])]

            self._current_run = RunState(
                issue_number=run_data["issue_number"],
                issue_url=run_data["issue_url"],
                base_branch=run_data["base_branch"],
                agents=agents,
                started_at=run_data["started_at"],
                completed_at=run_data.get("completed_at"),
                selected_agent=run_data.get("selected_agent"),
                pr_url=run_data.get("pr_url"),
            )

            logger.info(f"Loaded state for issue #{self._current_run.issue_number}")
            return self._current_run

        except json.JSONDecodeError as e:
            raise StateError(f"Corrupted state file: {e}") from e
        except Exception as e:
            raise StateError(f"Failed to load state: {e}") from e

    def get_current_run(self) -> RunState | None:
        """Get the current run state.

        Returns:
            Current RunState or None
        """
        return self._current_run

    def clear(self) -> None:
        """Clear current state and remove state file."""
        self._current_run = None
        if self.state_path.exists():
            self.state_path.unlink()
            logger.debug(f"Removed state file {self.state_path}")

    def can_recover(self) -> bool:
        """Check if there's a recoverable state.

        Returns:
            True if state exists and run is not completed
        """
        if not self.state_path.exists():
            return False

        try:
            state = self.load()
            return state is not None and state.completed_at is None
        except StateError:
            return False

    def recover(self) -> RunState | None:
        """Attempt to recover from persisted state.

        Returns:
            Recovered RunState or None if recovery not possible

        Raises:
            StateError: If state is corrupted
        """
        state = self.load()
        if not state:
            return None

        if state.completed_at:
            logger.info("Previous run was completed, starting fresh")
            self.clear()
            return None

        logger.info(f"Recovering run for issue #{state.issue_number}")
        return state

    def _persist(self) -> None:
        """Persist current state to disk.

        Raises:
            StateError: If persistence fails
        """
        if not self._current_run:
            return

        # Ensure parent directory exists
        self.state_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Convert dataclasses to dicts for JSON serialization
            state_dict = {
                "version": STATE_VERSION,
                "run": {
                    "issue_number": self._current_run.issue_number,
                    "issue_url": self._current_run.issue_url,
                    "base_branch": self._current_run.base_branch,
                    "agents": [asdict(agent) for agent in self._current_run.agents],
                    "started_at": self._current_run.started_at,
                    "completed_at": self._current_run.completed_at,
                    "selected_agent": self._current_run.selected_agent,
                    "pr_url": self._current_run.pr_url,
                },
            }

            with open(self.state_path, "w") as f:
                json.dump(state_dict, f, indent=2)

            logger.debug(f"Persisted state to {self.state_path}")

        except Exception as e:
            raise StateError(f"Failed to persist state: {e}") from e

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the current run state.

        Returns:
            Dictionary with run summary
        """
        if not self._current_run:
            return {"status": "no_active_run"}

        total_agents = len(self._current_run.agents)
        ready_agents = sum(1 for a in self._current_run.agents if a.status == "ready")
        failed_agents = sum(1 for a in self._current_run.agents if a.status == "failed")
        running_agents = sum(1 for a in self._current_run.agents if a.status == "running")
        pending_agents = sum(1 for a in self._current_run.agents if a.status == "pending")

        return {
            "status": "completed" if self._current_run.completed_at else "active",
            "issue_number": self._current_run.issue_number,
            "issue_url": self._current_run.issue_url,
            "started_at": self._current_run.started_at,
            "completed_at": self._current_run.completed_at,
            "total_agents": total_agents,
            "ready_agents": ready_agents,
            "failed_agents": failed_agents,
            "running_agents": running_agents,
            "pending_agents": pending_agents,
            "selected_agent": self._current_run.selected_agent,
            "pr_url": self._current_run.pr_url,
        }
