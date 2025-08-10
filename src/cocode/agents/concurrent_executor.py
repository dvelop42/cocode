"""Concurrent agent executor for running multiple agents in parallel.

This module provides high-level orchestration for running multiple agents
concurrently to solve the same issue, managing their lifecycle and collecting
results.
"""

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from cocode.agents.base import Agent, AgentStatus
from cocode.agents.lifecycle import AgentLifecycleManager, AgentState
from cocode.git.worktree import WorktreeManager

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result from executing multiple agents concurrently."""

    issue_number: int
    issue_url: str
    agent_results: dict[str, AgentStatus] = field(default_factory=dict)
    successful_agents: list[str] = field(default_factory=list)
    failed_agents: list[str] = field(default_factory=list)
    ready_agents: list[str] = field(default_factory=list)
    execution_time: float = 0.0
    errors: dict[str, str] = field(default_factory=dict)


class ConcurrentAgentExecutor:
    """Executes multiple agents concurrently to solve GitHub issues."""

    def __init__(
        self,
        repo_path: Path,
        max_concurrent_agents: int = 5,
        agent_timeout: int = 900,
    ) -> None:
        """Initialize the concurrent executor.

        Args:
            repo_path: Path to the git repository
            max_concurrent_agents: Maximum number of agents to run concurrently
            agent_timeout: Timeout for each agent in seconds (default: 15 minutes)
        """
        self.repo_path = repo_path
        self.max_concurrent_agents = max_concurrent_agents
        self.agent_timeout = agent_timeout
        self.lifecycle_manager = AgentLifecycleManager(
            max_concurrent_agents=max_concurrent_agents,
            default_timeout=agent_timeout,
        )
        self.worktree_manager = WorktreeManager(repo_path)
        self._completion_events: dict[str, threading.Event] = {}
        self._completion_statuses: dict[str, AgentStatus] = {}
        self._lock = threading.Lock()

    def execute_agents(
        self,
        agents: list[Agent],
        issue_number: int,
        issue_body: str,
        issue_url: str,
        base_branch: str = "main",
        progress_callback: Callable[[str, str], None] | None = None,
        output_callback: Callable[[str, str, str], None] | None = None,
    ) -> ExecutionResult:
        """Execute multiple agents concurrently on the same issue.

        Args:
            agents: List of agents to execute
            issue_number: GitHub issue number
            issue_body: Issue body content
            issue_url: URL to the GitHub issue
            base_branch: Base branch to create worktrees from
            progress_callback: Optional callback for progress updates (agent_name, state)
            output_callback: Optional callback for output (agent_name, stream, line)

        Returns:
            ExecutionResult with status and results from all agents
        """
        start_time = time.time()
        result = ExecutionResult(issue_number=issue_number, issue_url=issue_url)

        # Prepare worktrees for each agent
        logger.info(f"Preparing worktrees for {len(agents)} agents")
        worktrees = self._prepare_worktrees(agents, issue_number, base_branch)

        if not worktrees:
            logger.error("Failed to create worktrees")
            return result

        # Register agents with lifecycle manager
        for agent in agents:
            worktree_path = worktrees.get(agent.name)
            if worktree_path:
                self.lifecycle_manager.register_agent(
                    agent=agent,
                    worktree_path=worktree_path,
                    max_restarts=0,  # No automatic restarts for now
                )
                self._completion_events[agent.name] = threading.Event()

        # Start agents with simple scheduling respecting concurrency limits
        logger.info(
            f"Scheduling {len(agents)} agents (max concurrent: {self.max_concurrent_agents})"
        )
        pending = list(agents)  # not yet started
        started: set[str] = set()
        completed: set[str] = set()

        # Safety deadline: prevent infinite waits (allow some overhead for all batches)
        batches = max(
            1, (len(agents) + self.max_concurrent_agents - 1) // self.max_concurrent_agents
        )
        safety_deadline = time.time() + max(self.agent_timeout, 10) * batches

        def try_start(agent: Agent) -> bool:
            if progress_callback:
                progress_callback(agent.name, "starting")

            def make_stdout_callback(agent_name: str) -> Callable[[str], None] | None:
                if output_callback:
                    return lambda line: output_callback(agent_name, "stdout", line)
                return None

            def make_stderr_callback(agent_name: str) -> Callable[[str], None] | None:
                if output_callback:
                    return lambda line: output_callback(agent_name, "stderr", line)
                return None

            def make_completion_callback(agent_name: str) -> Callable[[AgentStatus], None]:
                return lambda status: self._handle_completion(agent_name, status, progress_callback)

            return self.lifecycle_manager.start_agent(
                agent_name=agent.name,
                issue_number=issue_number,
                issue_body=issue_body,
                issue_url=issue_url,
                stdout_callback=make_stdout_callback(agent.name),
                stderr_callback=make_stderr_callback(agent.name),
                completion_callback=make_completion_callback(agent.name),
            )

        while len(completed) < len(agents):
            # Attempt to start as many pending agents as possible
            made_progress = False
            for agent in list(pending):
                success = try_start(agent)
                if success:
                    started.add(agent.name)
                    pending.remove(agent)
                    made_progress = True
                else:
                    # Likely due to concurrency limit; will retry after some complete
                    continue

            # Check for completions among started agents
            for name in list(started):
                if name in self._completion_events and self._completion_events[name].is_set():
                    completed.add(name)
                    started.remove(name)

            if len(completed) >= len(agents):
                break

            if not made_progress and not started and pending:
                # Could not start anything and nothing running; mark remaining as failed to avoid hang
                logger.error("Could not start any agents; marking remaining as failed")
                for agent in pending:
                    result.failed_agents.append(agent.name)
                    result.errors[agent.name] = "Failed to start agent"
                    # Unblock waiters
                    if agent.name in self._completion_events:
                        self._completion_events[agent.name].set()
                    completed.add(agent.name)
                pending.clear()
                break

            # Safety timeout
            if time.time() > safety_deadline:
                logger.error(
                    "Execution exceeded safety deadline; marking unfinished agents as failed"
                )
                # Mark any not yet completed as failed
                for agent in pending:
                    result.failed_agents.append(agent.name)
                    result.errors[agent.name] = "Execution timed out before start"
                    if agent.name in self._completion_events:
                        self._completion_events[agent.name].set()
                    completed.add(agent.name)
                for _name in list(started):
                    # do not forcibly fail running ones; will be tallied by lifecycle status
                    pass
                break

            # Small sleep to avoid busy loop
            time.sleep(0.05)

        # Collect results
        for agent in agents:
            agent_info = self.lifecycle_manager.get_agent_info(agent.name)
            if agent_info and agent_info.status:
                status = agent_info.status
                result.agent_results[agent.name] = status

                if status.ready:
                    result.ready_agents.append(agent.name)
                    result.successful_agents.append(agent.name)
                elif status.exit_code == 0:
                    result.successful_agents.append(agent.name)
                else:
                    result.failed_agents.append(agent.name)
                    if status.error_message:
                        result.errors[agent.name] = status.error_message
            else:
                # If no status (e.g., never started), ensure it's marked failed
                if (
                    agent.name not in result.agent_results
                    and agent.name not in result.failed_agents
                ):
                    result.failed_agents.append(agent.name)
                    result.errors[agent.name] = "No status available"

        result.execution_time = time.time() - start_time
        logger.info(
            f"Execution completed in {result.execution_time:.1f}s: "
            f"{len(result.successful_agents)} successful, "
            f"{len(result.failed_agents)} failed, "
            f"{len(result.ready_agents)} ready"
        )

        return result

    def _prepare_worktrees(
        self, agents: list[Agent], issue_number: int, base_branch: str
    ) -> dict[str, Path]:
        """Prepare git worktrees for each agent.

        Args:
            agents: List of agents needing worktrees
            issue_number: Issue number for branch naming
            base_branch: Base branch to create worktrees from

        Returns:
            Dictionary mapping agent names to worktree paths
        """
        worktrees = {}

        for agent in agents:
            branch_name = f"cocode/{issue_number}-{agent.name}"

            try:
                # Create worktree for agent
                worktree_path = self.worktree_manager.create_worktree(
                    branch_name=branch_name,
                    agent_name=agent.name,
                )
                worktrees[agent.name] = worktree_path
                logger.info(f"Created worktree for {agent.name} at {worktree_path}")
            except Exception as e:
                logger.error(f"Failed to create worktree for {agent.name}: {e}")

        return worktrees

    def _handle_completion(
        self,
        agent_name: str,
        status: AgentStatus,
        progress_callback: Callable[[str, str], None] | None,
    ) -> None:
        """Handle agent completion.

        Args:
            agent_name: Name of the completed agent
            status: Completion status
            progress_callback: Optional progress callback
        """
        with self._lock:
            self._completion_statuses[agent_name] = status
            self._completion_events[agent_name].set()

        # Notify progress
        if progress_callback:
            if status.ready:
                state = "ready"
            elif status.exit_code == 0:
                state = "completed"
            else:
                state = "failed"
            progress_callback(agent_name, state)

        logger.info(f"Agent {agent_name} completed with status: {status.exit_code}")

    def _wait_for_all_completions(
        self,
        agents: list[Agent],
        progress_callback: Callable[[str, str], None] | None,
        poll_interval: float = 0.5,
    ) -> None:
        """Wait for all agents to complete.

        Args:
            agents: List of agents to wait for
            progress_callback: Optional progress callback
            poll_interval: Interval to poll status in seconds
        """
        pending_agents = {agent.name for agent in agents}

        while pending_agents:
            completed_in_batch = []

            for agent_name in pending_agents:
                if agent_name in self._completion_events:
                    event = self._completion_events[agent_name]
                    if event.is_set():
                        completed_in_batch.append(agent_name)

            # Remove completed agents
            for agent_name in completed_in_batch:
                pending_agents.remove(agent_name)
                logger.debug(f"Agent {agent_name} finished, {len(pending_agents)} remaining")

            # Update progress for running agents
            if progress_callback and pending_agents:
                for agent_name in pending_agents:
                    state = self.lifecycle_manager.get_agent_state(agent_name)
                    if state == AgentState.RUNNING:
                        progress_callback(agent_name, "running")

            if pending_agents:
                time.sleep(poll_interval)

    def stop_all_agents(self, force: bool = False) -> None:
        """Stop all running agents.

        Args:
            force: If True, forcefully terminate agents
        """
        logger.info("Stopping all agents")
        self.lifecycle_manager.shutdown_all(force=force)

    def cleanup_worktrees(self, agents: list[Agent]) -> None:
        """Clean up worktrees for the given agents.

        Args:
            agents: List of agents whose worktrees should be cleaned
        """
        for agent in agents:
            worktree_path = self.repo_path.parent / f"cocode_{agent.name}"
            try:
                self.worktree_manager.remove_worktree(worktree_path)
                logger.info(f"Removed worktree for {agent.name}")
            except Exception as e:
                logger.warning(f"Failed to remove worktree for {agent.name}: {e}")

    def get_agent_status(self, agent_name: str) -> AgentStatus | None:
        """Get the current status of an agent.

        Args:
            agent_name: Name of the agent

        Returns:
            Agent status or None if not found
        """
        info = self.lifecycle_manager.get_agent_info(agent_name)
        return info.status if info else None

    def restart_agent(
        self,
        agent_name: str,
        issue_number: int,
        issue_body: str,
        issue_url: str,
    ) -> bool:
        """Restart a specific agent.

        Args:
            agent_name: Name of the agent to restart
            issue_number: GitHub issue number
            issue_body: Issue body content
            issue_url: URL to the GitHub issue

        Returns:
            True if restart successful, False otherwise
        """
        return self.lifecycle_manager.restart_agent(
            agent_name=agent_name,
            issue_number=issue_number,
            issue_body=issue_body,
            issue_url=issue_url,
        )
