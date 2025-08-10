"""Agent lifecycle manager for handling start/stop/restart operations."""

import atexit
import logging
import signal
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from cocode.agents.base import Agent, AgentStatus
from cocode.agents.runner import AgentRunner

logger = logging.getLogger(__name__)


class AgentState(Enum):
    """States an agent can be in during its lifecycle."""

    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"
    READY = "ready"


@dataclass
class AgentLifecycleInfo:
    """Complete lifecycle information for an agent."""

    agent: Agent
    state: AgentState = AgentState.IDLE
    status: AgentStatus | None = None
    worktree_path: Path | None = None
    process: subprocess.Popen[str] | None = None
    thread: threading.Thread | None = None
    output_lines: list[str] = field(default_factory=list)
    error: str | None = None
    restart_count: int = 0
    max_restarts: int = 3


class AgentLifecycleManager:
    """Manages the lifecycle of multiple agents."""

    def __init__(
        self,
        max_concurrent_agents: int = 5,
        default_timeout: int = 900,
    ) -> None:
        """Initialize the lifecycle manager.

        Args:
            max_concurrent_agents: Maximum number of agents to run concurrently
            default_timeout: Default timeout for agent execution in seconds
        """
        self.max_concurrent_agents = max_concurrent_agents
        self.default_timeout = default_timeout
        self.agents: dict[str, AgentLifecycleInfo] = {}
        self.runner = AgentRunner()
        self._lock = threading.Lock()
        self._shutdown_requested = False
        self._running_count = 0

        # Register cleanup handlers
        atexit.register(self.shutdown_all)
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, initiating shutdown")
        self.shutdown_all()

    def register_agent(
        self,
        agent: Agent,
        worktree_path: Path,
        max_restarts: int = 3,
    ) -> None:
        """Register an agent for lifecycle management.

        Args:
            agent: The agent to register
            worktree_path: Path to the agent's worktree
            max_restarts: Maximum number of restart attempts
        """
        with self._lock:
            if agent.name in self.agents:
                logger.warning(f"Agent {agent.name} already registered, updating")

            self.agents[agent.name] = AgentLifecycleInfo(
                agent=agent,
                worktree_path=worktree_path,
                max_restarts=max_restarts,
            )
            logger.info(f"Registered agent {agent.name}")

    def start_agent(
        self,
        agent_name: str,
        issue_number: int,
        issue_body: str,
        issue_url: str,
        stdout_callback: Callable[[str], None] | None = None,
        stderr_callback: Callable[[str], None] | None = None,
        completion_callback: Callable[[AgentStatus], None] | None = None,
    ) -> bool:
        """Start an agent asynchronously.

        Args:
            agent_name: Name of the agent to start
            issue_number: GitHub issue number
            issue_body: Issue body content
            issue_url: URL to the GitHub issue
            stdout_callback: Optional callback for stdout lines
            stderr_callback: Optional callback for stderr lines
            completion_callback: Optional callback when agent completes

        Returns:
            True if agent started successfully, False otherwise
        """
        with self._lock:
            if agent_name not in self.agents:
                logger.error(f"Agent {agent_name} not registered")
                return False

            info = self.agents[agent_name]

            # Check if already running
            if info.state in (AgentState.RUNNING, AgentState.STARTING):
                logger.warning(f"Agent {agent_name} is already running")
                return False

            # Check concurrent limit
            if self._running_count >= self.max_concurrent_agents:
                logger.warning(f"Maximum concurrent agents ({self.max_concurrent_agents}) reached")
                return False

            # Update state
            info.state = AgentState.STARTING
            info.output_lines.clear()
            info.error = None
            self._running_count += 1

        # Start agent in a separate thread
        thread = threading.Thread(
            target=self._run_agent,
            args=(
                agent_name,
                issue_number,
                issue_body,
                issue_url,
                stdout_callback,
                stderr_callback,
                completion_callback,
            ),
            daemon=True,
        )
        info.thread = thread
        thread.start()

        logger.info(f"Started agent {agent_name}")
        return True

    def _run_agent(
        self,
        agent_name: str,
        issue_number: int,
        issue_body: str,
        issue_url: str,
        stdout_callback: Callable[[str], None] | None,
        stderr_callback: Callable[[str], None] | None,
        completion_callback: Callable[[AgentStatus], None] | None,
    ) -> None:
        """Run an agent (internal method for thread execution)."""
        info = self.agents[agent_name]

        try:
            # Update state
            with self._lock:
                info.state = AgentState.RUNNING

            # Collect output
            def collect_stdout(line: str) -> None:
                info.output_lines.append(line)
                if stdout_callback:
                    stdout_callback(line)

            def collect_stderr(line: str) -> None:
                info.output_lines.append(f"[stderr] {line}")
                if stderr_callback:
                    stderr_callback(line)

            # Run the agent
            status = self.runner.run_agent(
                agent=info.agent,
                worktree_path=info.worktree_path,
                issue_number=issue_number,
                issue_body=issue_body,
                issue_url=issue_url,
                timeout=self.default_timeout,
                stdout_callback=collect_stdout,
                stderr_callback=collect_stderr,
            )

            info.status = status

            # Update state based on result
            with self._lock:
                if status.ready:
                    info.state = AgentState.READY
                elif status.exit_code == 0:
                    info.state = AgentState.COMPLETED
                else:
                    info.state = AgentState.FAILED
                    info.error = status.error_message

            # Call completion callback
            if completion_callback:
                completion_callback(status)

        except Exception as e:
            logger.error(f"Error running agent {agent_name}: {e}")
            with self._lock:
                info.state = AgentState.FAILED
                info.error = str(e)
        finally:
            with self._lock:
                self._running_count -= 1

    def stop_agent(self, agent_name: str, force: bool = False) -> bool:
        """Stop a running agent.

        Args:
            agent_name: Name of the agent to stop
            force: If True, forcefully terminate the agent

        Returns:
            True if stop initiated successfully, False otherwise
        """
        with self._lock:
            if agent_name not in self.agents:
                logger.error(f"Agent {agent_name} not registered")
                return False

            info = self.agents[agent_name]

            if info.state not in (AgentState.RUNNING, AgentState.STARTING):
                logger.warning(f"Agent {agent_name} is not running")
                return False

            info.state = AgentState.STOPPING

        # Stop the thread (this is a simplified version)
        # In a real implementation, we'd need to handle subprocess termination
        if info.thread and info.thread.is_alive():
            logger.info(f"Stopping agent {agent_name}")
            # Thread will complete on its own or timeout
            # For force stop, we'd need to track the subprocess and terminate it

        with self._lock:
            info.state = AgentState.STOPPED

        logger.info(f"Stopped agent {agent_name}")
        return True

    def restart_agent(
        self,
        agent_name: str,
        issue_number: int,
        issue_body: str,
        issue_url: str,
        stdout_callback: Callable[[str], None] | None = None,
        stderr_callback: Callable[[str], None] | None = None,
        completion_callback: Callable[[AgentStatus], None] | None = None,
    ) -> bool:
        """Restart an agent.

        Args:
            agent_name: Name of the agent to restart
            issue_number: GitHub issue number
            issue_body: Issue body content
            issue_url: URL to the GitHub issue
            stdout_callback: Optional callback for stdout lines
            stderr_callback: Optional callback for stderr lines
            completion_callback: Optional callback when agent completes

        Returns:
            True if restart initiated successfully, False otherwise
        """
        with self._lock:
            if agent_name not in self.agents:
                logger.error(f"Agent {agent_name} not registered")
                return False

            info = self.agents[agent_name]

            # Check restart limit
            if info.restart_count >= info.max_restarts:
                logger.error(f"Agent {agent_name} exceeded max restarts ({info.max_restarts})")
                return False

            info.restart_count += 1

        logger.info(f"Restarting agent {agent_name} (attempt {info.restart_count})")

        # Stop if running
        if info.state in (AgentState.RUNNING, AgentState.STARTING):
            self.stop_agent(agent_name)

        # Wait a moment for cleanup
        time.sleep(0.5)

        # Start again
        return self.start_agent(
            agent_name,
            issue_number,
            issue_body,
            issue_url,
            stdout_callback,
            stderr_callback,
            completion_callback,
        )

    def get_agent_state(self, agent_name: str) -> AgentState | None:
        """Get the current state of an agent.

        Args:
            agent_name: Name of the agent

        Returns:
            Current state of the agent or None if not found
        """
        with self._lock:
            if agent_name in self.agents:
                return self.agents[agent_name].state
            return None

    def get_agent_info(self, agent_name: str) -> AgentLifecycleInfo | None:
        """Get complete lifecycle info for an agent.

        Args:
            agent_name: Name of the agent

        Returns:
            Complete lifecycle info or None if not found
        """
        with self._lock:
            return self.agents.get(agent_name)

    def get_all_agents(self) -> dict[str, AgentLifecycleInfo]:
        """Get all registered agents and their info.

        Returns:
            Dictionary of agent names to their lifecycle info
        """
        with self._lock:
            return self.agents.copy()

    def is_any_running(self) -> bool:
        """Check if any agents are currently running.

        Returns:
            True if any agents are running, False otherwise
        """
        with self._lock:
            return any(
                info.state in (AgentState.RUNNING, AgentState.STARTING)
                for info in self.agents.values()
            )

    def wait_for_completion(self, timeout: float | None = None) -> bool:
        """Wait for all agents to complete.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if all agents completed, False if timeout
        """
        import time

        start_time = time.time()

        while self.is_any_running():
            if timeout and (time.time() - start_time) > timeout:
                return False
            time.sleep(0.5)

        return True

    def shutdown_all(self, force: bool = False) -> None:
        """Shutdown all agents gracefully.

        Args:
            force: If True, forcefully terminate all agents
        """
        if self._shutdown_requested:
            return

        self._shutdown_requested = True
        logger.info("Shutting down all agents")

        with self._lock:
            agent_names = list(self.agents.keys())

        for agent_name in agent_names:
            info = self.agents[agent_name]
            if info.state in (AgentState.RUNNING, AgentState.STARTING):
                self.stop_agent(agent_name, force=force)

        # Wait for threads to complete (with timeout)
        if not force:
            self.wait_for_completion(timeout=10)

        # Cleanup
        self.runner.cleanup()
        logger.info("All agents shut down")

    def reset_agent(self, agent_name: str) -> bool:
        """Reset an agent's state and counters.

        Args:
            agent_name: Name of the agent to reset

        Returns:
            True if reset successfully, False otherwise
        """
        with self._lock:
            if agent_name not in self.agents:
                logger.error(f"Agent {agent_name} not registered")
                return False

            info = self.agents[agent_name]

            if info.state in (AgentState.RUNNING, AgentState.STARTING):
                logger.warning(f"Cannot reset running agent {agent_name}")
                return False

            # Reset state
            info.state = AgentState.IDLE
            info.status = None
            info.output_lines.clear()
            info.error = None
            info.restart_count = 0

        logger.info(f"Reset agent {agent_name}")
        return True
