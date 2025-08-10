"""Concurrent agent executor for running multiple agents in parallel.

This module provides high-level orchestration for running multiple agents
concurrently to solve the same issue, managing their lifecycle and collecting
results.
"""

import logging
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cocode.agents.base import Agent, AgentStatus
from cocode.agents.lifecycle import AgentLifecycleManager, AgentState
from cocode.git.worktree import WorktreeError, WorktreeManager

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

    # Resource limit constants
    MIN_CONCURRENT_AGENTS = 1
    MAX_CONCURRENT_AGENTS = 20
    # Allow short timeouts for tests and fast local runs
    MIN_TIMEOUT = 1
    MAX_TIMEOUT = 3600
    MAX_ISSUE_NUMBER = 999999

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

        Raises:
            ValueError: If parameters are out of valid ranges
        """
        self.repo_path = repo_path

        # Validate parameters
        if not (self.MIN_CONCURRENT_AGENTS <= max_concurrent_agents <= self.MAX_CONCURRENT_AGENTS):
            raise ValueError(
                f"max_concurrent_agents must be between {self.MIN_CONCURRENT_AGENTS} "
                f"and {self.MAX_CONCURRENT_AGENTS}"
            )
        if not (self.MIN_TIMEOUT <= agent_timeout <= self.MAX_TIMEOUT):
            raise ValueError(
                f"agent_timeout must be between {self.MIN_TIMEOUT} and {self.MAX_TIMEOUT}"
            )

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
        self._cleanup_on_exit = True

    def __enter__(self) -> "ConcurrentAgentExecutor":
        """Enter context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit context manager and clean up resources."""
        if self._cleanup_on_exit:
            self.stop_all_agents(force=True)
            self._cleanup_resources()

    def _cleanup_resources(self) -> None:
        """Clean up internal resources."""
        with self._lock:
            self._completion_events.clear()
            self._completion_statuses.clear()

    def _validate_inputs(
        self,
        agents: list[Agent],
        issue_number: int,
        issue_body: str,
        issue_url: str,
    ) -> None:
        """Validate execution inputs.

        Args:
            agents: List of agents to validate
            issue_number: GitHub issue number
            issue_body: Issue body content
            issue_url: URL to the GitHub issue

        Raises:
            ValueError: If inputs are invalid
        """
        if not agents:
            raise ValueError("Agent list cannot be empty")

        agent_names = [agent.name for agent in agents]
        if len(set(agent_names)) != len(agent_names):
            duplicates = [name for name in agent_names if agent_names.count(name) > 1]
            raise ValueError(f"Duplicate agent names not allowed: {duplicates}")

        if not (1 <= issue_number <= self.MAX_ISSUE_NUMBER):
            raise ValueError(f"Invalid issue number: {issue_number}")

        if not issue_body:
            raise ValueError("Issue body cannot be empty")

        if not issue_url:
            raise ValueError("Issue URL cannot be empty")

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

        Raises:
            ValueError: If inputs are invalid
        """
        # Validate inputs
        self._validate_inputs(agents, issue_number, issue_body, issue_url)

        start_time = time.time()
        result = ExecutionResult(issue_number=issue_number, issue_url=issue_url)

        # Prepare worktrees for each agent
        logger.info(f"Preparing worktrees for {len(agents)} agents")
        worktrees = self._prepare_worktrees(agents, issue_number, base_branch)

        if not worktrees:
            logger.error("Failed to create worktrees")
            return result

        # Register agents with lifecycle manager
        self._register_agents(agents, worktrees)

        # Execute agents with scheduling
        self._execute_with_scheduling(
            agents=agents,
            issue_number=issue_number,
            issue_body=issue_body,
            issue_url=issue_url,
            result=result,
            progress_callback=progress_callback,
            output_callback=output_callback,
        )

        # Ensure all agent threads have fully settled before collecting results
        try:
            # Use agent_timeout as an upper bound to avoid hanging
            self.lifecycle_manager.wait_for_completion(timeout=float(self.agent_timeout))
        except Exception:
            # Proceed to collect what we can; robustness over strictness
            pass

        # Collect results using batch operation
        self._collect_results(agents, result)

        result.execution_time = time.time() - start_time
        logger.info(
            f"Execution completed in {result.execution_time:.1f}s: "
            f"{len(result.successful_agents)} successful, "
            f"{len(result.failed_agents)} failed, "
            f"{len(result.ready_agents)} ready"
        )

        return result

    def _register_agents(
        self,
        agents: list[Agent],
        worktrees: dict[str, Path],
    ) -> None:
        """Register agents with lifecycle manager.

        Args:
            agents: List of agents to register
            worktrees: Dictionary mapping agent names to worktree paths
        """
        for agent in agents:
            worktree_path = worktrees.get(agent.name)
            if worktree_path:
                self.lifecycle_manager.register_agent(
                    agent=agent,
                    worktree_path=worktree_path,
                    max_restarts=0,  # No automatic restarts for now
                )
                self._completion_events[agent.name] = threading.Event()

    def _execute_with_scheduling(
        self,
        agents: list[Agent],
        issue_number: int,
        issue_body: str,
        issue_url: str,
        result: ExecutionResult,
        progress_callback: Callable[[str, str], None] | None,
        output_callback: Callable[[str, str, str], None] | None,
    ) -> None:
        """Execute agents with scheduling respecting concurrency limits.

        Args:
            agents: List of agents to execute
            issue_number: GitHub issue number
            issue_body: Issue body content
            issue_url: URL to the GitHub issue
            result: ExecutionResult to populate
            progress_callback: Optional progress callback
            output_callback: Optional output callback
        """
        logger.info(
            f"Scheduling {len(agents)} agents (max concurrent: {self.max_concurrent_agents})"
        )

        pending = list(agents)  # not yet started
        started: set[str] = set()
        completed: set[str] = set()

        # Safety deadline: prevent infinite waits
        batches = max(
            1, (len(agents) + self.max_concurrent_agents - 1) // self.max_concurrent_agents
        )
        safety_deadline = time.time() + max(self.agent_timeout, 10) * batches

        # Exponential backoff parameters
        attempt = 0
        max_sleep = 0.5

        while len(completed) < len(agents):
            # First, check for any completions to free up capacity
            newly_completed = self._check_completions(started)
            for name in newly_completed:
                completed.add(name)
                started.remove(name)

            if len(completed) >= len(agents):
                break

            # Then, try to schedule next batch (after freeing capacity)
            made_progress = self._schedule_next_batch(
                pending=pending,
                started=started,
                issue_number=issue_number,
                issue_body=issue_body,
                issue_url=issue_url,
                progress_callback=progress_callback,
                output_callback=output_callback,
            )

            # Handle stuck state only if nothing is running and we couldn't start new ones
            if not made_progress and not started and pending:
                try:
                    any_running = self.lifecycle_manager.is_any_running()
                except Exception:
                    any_running = False
                if not any_running:
                    self._handle_stuck_agents(pending, result, completed)
                    break

            # Check safety timeout
            if time.time() > safety_deadline:
                self._handle_timeout(pending, result, completed)
                break

            # Exponential backoff sleep
            if not made_progress and not newly_completed:
                attempt += 1
                sleep_time = min(0.01 * (1.1**attempt), max_sleep)
            else:
                attempt = 0
                sleep_time = 0.01

            time.sleep(sleep_time)

    def _schedule_next_batch(
        self,
        pending: list[Agent],
        started: set[str],
        issue_number: int,
        issue_body: str,
        issue_url: str,
        progress_callback: Callable[[str, str], None] | None,
        output_callback: Callable[[str, str, str], None] | None,
    ) -> bool:
        """Schedule next batch of agents respecting concurrency limits.

        Returns:
            True if any agents were started, False otherwise
        """
        made_progress = False

        for agent in list(pending):
            if len(started) >= self.max_concurrent_agents:
                break

            success = self._start_agent(
                agent=agent,
                issue_number=issue_number,
                issue_body=issue_body,
                issue_url=issue_url,
                progress_callback=progress_callback,
                output_callback=output_callback,
            )

            if success:
                started.add(agent.name)
                pending.remove(agent)
                made_progress = True

        return made_progress

    def _start_agent(
        self,
        agent: Agent,
        issue_number: int,
        issue_body: str,
        issue_url: str,
        progress_callback: Callable[[str, str], None] | None,
        output_callback: Callable[[str, str, str], None] | None,
    ) -> bool:
        """Start a single agent.

        Returns:
            True if agent started successfully, False otherwise
        """
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

    def _check_completions(self, started: set[str]) -> set[str]:
        """Check for completed agents.

        Args:
            started: Set of started agent names

        Returns:
            Set of newly completed agent names
        """
        completed = set()
        for name in list(started):
            if name in self._completion_events and self._completion_events[name].is_set():
                completed.add(name)
        return completed

    def _handle_stuck_agents(
        self,
        pending: list[Agent],
        result: ExecutionResult,
        completed: set[str],
    ) -> None:
        """Handle agents that couldn't be started."""
        logger.error("Could not start any agents; marking remaining as failed")
        for agent in pending:
            result.failed_agents.append(agent.name)
            result.errors[agent.name] = "Failed to start agent"
            if agent.name in self._completion_events:
                self._completion_events[agent.name].set()
            completed.add(agent.name)
        pending.clear()

    def _handle_timeout(
        self,
        pending: list[Agent],
        result: ExecutionResult,
        completed: set[str],
    ) -> None:
        """Handle execution timeout."""
        logger.error("Execution exceeded safety deadline; marking unfinished agents as failed")
        for agent in pending:
            result.failed_agents.append(agent.name)
            result.errors[agent.name] = "Execution timed out before start"
            if agent.name in self._completion_events:
                self._completion_events[agent.name].set()
            completed.add(agent.name)

    def _collect_results(
        self,
        agents: list[Agent],
        result: ExecutionResult,
    ) -> None:
        """Collect results from all agents using batch operations.

        Args:
            agents: List of agents
            result: ExecutionResult to populate
        """
        # Try batch collection first, but be resilient to mocks/non-mapping returns
        all_statuses: dict[str, AgentStatus] = {}
        try:
            statuses = self._get_all_agent_statuses()
            if isinstance(statuses, dict):
                all_statuses = statuses
        except Exception as e:  # pragma: no cover - defensive against unusual mocks
            logger.debug(f"Batch status collection failed, falling back: {e}")

        # Fallback to per-agent lookup if batch is empty or incomplete
        if len(all_statuses) < len(agents):
            for agent in agents:
                if agent.name in all_statuses:
                    continue
                try:
                    info = self.lifecycle_manager.get_agent_info(agent.name)
                    if info and info.status:
                        all_statuses[agent.name] = info.status
                except Exception as e:  # pragma: no cover - robustness with mocks
                    logger.debug(f"Per-agent status lookup failed for {agent.name}: {e}")

        for agent in agents:
            status = all_statuses.get(agent.name)
            if status:
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
                # If no status, ensure it's marked failed
                if (
                    agent.name not in result.agent_results
                    and agent.name not in result.failed_agents
                ):
                    result.failed_agents.append(agent.name)
                    result.errors[agent.name] = "No status available"

    def _get_all_agent_statuses(self) -> dict[str, AgentStatus]:
        """Get statuses for all registered agents in batch.

        Returns:
            Dictionary mapping agent names to their statuses
        """
        statuses = {}
        all_agents = self.lifecycle_manager.get_all_agents()

        for agent_name, info in all_agents.items():
            if info.status:
                statuses[agent_name] = info.status

        return statuses

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
            except (WorktreeError, subprocess.CalledProcessError, OSError, Exception) as e:
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
            except (WorktreeError, subprocess.CalledProcessError, OSError, Exception) as e:
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
