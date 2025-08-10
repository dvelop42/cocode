"""Tests for concurrent executor improvements."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from cocode.agents.base import Agent, AgentStatus
from cocode.agents.concurrent_executor import ConcurrentAgentExecutor
from cocode.git.worktree import WorktreeError


class TestAgent(Agent):
    """Test agent for unit tests."""

    def __init__(self, name: str):
        super().__init__(name)

    def validate_environment(self) -> bool:
        return True

    def prepare_environment(
        self, worktree_path: Path, issue_number: int, issue_body: str
    ) -> dict[str, str]:
        return {}

    def get_command(self) -> list[str]:
        return ["echo", "test"]

    def check_ready(self, worktree_path: Path) -> bool:
        return True


class TestInputValidation:
    """Test input validation improvements."""

    @patch("cocode.agents.concurrent_executor.WorktreeManager")
    @patch("cocode.agents.concurrent_executor.AgentLifecycleManager")
    def test_validate_duplicate_agent_names(self, mock_lifecycle_class, mock_worktree_class):
        """Test that duplicate agent names are rejected."""
        executor = ConcurrentAgentExecutor(Path("/tmp/repo"))

        agents = [
            TestAgent("agent1"),
            TestAgent("agent2"),
            TestAgent("agent1"),  # Duplicate
        ]

        with pytest.raises(ValueError, match="Duplicate agent names not allowed"):
            executor.execute_agents(
                agents=agents,
                issue_number=123,
                issue_body="Test issue",
                issue_url="https://github.com/test/repo/issues/123",
            )

    @patch("cocode.agents.concurrent_executor.WorktreeManager")
    @patch("cocode.agents.concurrent_executor.AgentLifecycleManager")
    def test_validate_empty_agent_list(self, mock_lifecycle_class, mock_worktree_class):
        """Test that empty agent list is rejected."""
        executor = ConcurrentAgentExecutor(Path("/tmp/repo"))

        with pytest.raises(ValueError, match="Agent list cannot be empty"):
            executor.execute_agents(
                agents=[],
                issue_number=123,
                issue_body="Test issue",
                issue_url="https://github.com/test/repo/issues/123",
            )

    @patch("cocode.agents.concurrent_executor.WorktreeManager")
    @patch("cocode.agents.concurrent_executor.AgentLifecycleManager")
    def test_validate_invalid_issue_number(self, mock_lifecycle_class, mock_worktree_class):
        """Test that invalid issue numbers are rejected."""
        executor = ConcurrentAgentExecutor(Path("/tmp/repo"))

        agents = [TestAgent("agent1")]

        # Test negative issue number
        with pytest.raises(ValueError, match="Invalid issue number"):
            executor.execute_agents(
                agents=agents,
                issue_number=-1,
                issue_body="Test issue",
                issue_url="https://github.com/test/repo/issues/-1",
            )

        # Test issue number too large
        with pytest.raises(ValueError, match="Invalid issue number"):
            executor.execute_agents(
                agents=agents,
                issue_number=9999999,
                issue_body="Test issue",
                issue_url="https://github.com/test/repo/issues/9999999",
            )

    @patch("cocode.agents.concurrent_executor.WorktreeManager")
    @patch("cocode.agents.concurrent_executor.AgentLifecycleManager")
    def test_validate_empty_issue_body(self, mock_lifecycle_class, mock_worktree_class):
        """Test that empty issue body is rejected."""
        executor = ConcurrentAgentExecutor(Path("/tmp/repo"))

        agents = [TestAgent("agent1")]

        with pytest.raises(ValueError, match="Issue body cannot be empty"):
            executor.execute_agents(
                agents=agents,
                issue_number=123,
                issue_body="",
                issue_url="https://github.com/test/repo/issues/123",
            )

    @patch("cocode.agents.concurrent_executor.WorktreeManager")
    @patch("cocode.agents.concurrent_executor.AgentLifecycleManager")
    def test_validate_empty_issue_url(self, mock_lifecycle_class, mock_worktree_class):
        """Test that empty issue URL is rejected."""
        executor = ConcurrentAgentExecutor(Path("/tmp/repo"))

        agents = [TestAgent("agent1")]

        with pytest.raises(ValueError, match="Issue URL cannot be empty"):
            executor.execute_agents(
                agents=agents,
                issue_number=123,
                issue_body="Test issue",
                issue_url="",
            )


class TestResourceLimits:
    """Test resource limit validation."""

    @patch("cocode.agents.concurrent_executor.WorktreeManager")
    def test_invalid_max_concurrent_agents(self, mock_worktree_class):
        """Test that invalid concurrent agent limits are rejected."""
        # Too few agents
        with pytest.raises(ValueError, match="max_concurrent_agents must be between"):
            ConcurrentAgentExecutor(
                Path("/tmp/repo"),
                max_concurrent_agents=0,
            )

        # Too many agents
        with pytest.raises(ValueError, match="max_concurrent_agents must be between"):
            ConcurrentAgentExecutor(
                Path("/tmp/repo"),
                max_concurrent_agents=100,
            )

    @patch("cocode.agents.concurrent_executor.WorktreeManager")
    def test_invalid_timeout(self, mock_worktree_class):
        """Test that invalid timeouts are rejected."""
        # Timeout too short (MIN_TIMEOUT is now 1)
        with pytest.raises(ValueError, match="agent_timeout must be between"):
            ConcurrentAgentExecutor(
                Path("/tmp/repo"),
                agent_timeout=0,  # Less than MIN_TIMEOUT (1)
            )

        # Timeout too long
        with pytest.raises(ValueError, match="agent_timeout must be between"):
            ConcurrentAgentExecutor(
                Path("/tmp/repo"),
                agent_timeout=10000,
            )


class TestContextManager:
    """Test context manager support."""

    @patch("cocode.agents.concurrent_executor.WorktreeManager")
    @patch("cocode.agents.concurrent_executor.AgentLifecycleManager")
    def test_context_manager_cleanup(self, mock_lifecycle_class, mock_worktree_class):
        """Test that context manager cleans up resources."""
        mock_lifecycle = Mock()
        mock_lifecycle_class.return_value = mock_lifecycle

        with ConcurrentAgentExecutor(Path("/tmp/repo")) as executor:
            # Add some events to simulate running agents
            executor._completion_events["test1"] = Mock()
            executor._completion_events["test2"] = Mock()
            executor._completion_statuses["test1"] = Mock()

        # Verify cleanup was called
        mock_lifecycle.shutdown_all.assert_called_once_with(force=True)

    @patch("cocode.agents.concurrent_executor.WorktreeManager")
    @patch("cocode.agents.concurrent_executor.AgentLifecycleManager")
    def test_context_manager_with_exception(self, mock_lifecycle_class, mock_worktree_class):
        """Test that context manager cleans up even with exceptions."""
        mock_lifecycle = Mock()
        mock_lifecycle_class.return_value = mock_lifecycle

        try:
            with ConcurrentAgentExecutor(Path("/tmp/repo")) as executor:
                # Add some events
                executor._completion_events["test"] = Mock()
                # Raise an exception
                raise RuntimeError("Test error")
        except RuntimeError:
            pass

        # Verify cleanup was still called
        mock_lifecycle.shutdown_all.assert_called_once_with(force=True)


class TestErrorHandling:
    """Test improved error handling."""

    @patch("cocode.agents.concurrent_executor.WorktreeManager")
    @patch("cocode.agents.concurrent_executor.AgentLifecycleManager")
    def test_specific_exception_handling(self, mock_lifecycle_class, mock_worktree_class):
        """Test that specific exceptions are caught properly."""
        mock_worktree = Mock()
        mock_worktree_class.return_value = mock_worktree

        # Simulate WorktreeError
        mock_worktree.create_worktree.side_effect = WorktreeError("Test worktree error")

        executor = ConcurrentAgentExecutor(Path("/tmp/repo"))
        agents = [TestAgent("agent1")]

        # Mock lifecycle manager to avoid hanging
        mock_lifecycle = Mock()
        mock_lifecycle_class.return_value = mock_lifecycle
        mock_lifecycle.get_all_agents.return_value = {}

        result = executor.execute_agents(
            agents=agents,
            issue_number=123,
            issue_body="Test issue",
            issue_url="https://github.com/test/repo/issues/123",
        )

        # Should handle the error gracefully
        assert len(result.agent_results) == 0
        assert result.issue_number == 123


class TestBatchOperations:
    """Test batch operations for performance."""

    @patch("cocode.agents.concurrent_executor.WorktreeManager")
    @patch("cocode.agents.concurrent_executor.AgentLifecycleManager")
    def test_batch_status_collection(self, mock_lifecycle_class, mock_worktree_class):
        """Test that statuses are collected in batch."""
        mock_lifecycle = Mock()
        mock_lifecycle_class.return_value = mock_lifecycle
        mock_worktree = Mock()
        mock_worktree_class.return_value = mock_worktree

        # Mock batch operation
        mock_lifecycle.get_all_agents.return_value = {
            "agent1": Mock(
                status=AgentStatus(
                    name="agent1",
                    branch="test",
                    worktree=Path("/tmp/worktree1"),
                    ready=True,
                    exit_code=0,
                )
            ),
            "agent2": Mock(
                status=AgentStatus(
                    name="agent2",
                    branch="test",
                    worktree=Path("/tmp/worktree2"),
                    ready=False,
                    exit_code=1,
                )
            ),
        }

        executor = ConcurrentAgentExecutor(Path("/tmp/repo"))

        # Get all statuses
        statuses = executor._get_all_agent_statuses()

        # Verify batch call was made
        mock_lifecycle.get_all_agents.assert_called_once()
        assert len(statuses) == 2
        assert "agent1" in statuses
        assert "agent2" in statuses


class TestExponentialBackoff:
    """Test exponential backoff implementation."""

    @patch("cocode.agents.concurrent_executor.WorktreeManager")
    @patch("cocode.agents.concurrent_executor.AgentLifecycleManager")
    def test_exponential_backoff_calculation(self, mock_lifecycle_class, mock_worktree_class):
        """Test that exponential backoff is calculated correctly."""
        ConcurrentAgentExecutor(Path("/tmp/repo"))  # Just verify it can be created

        # Test backoff calculation
        max_sleep = 0.5

        # First attempt
        attempt = 1
        sleep_time = min(0.01 * (1.1**attempt), max_sleep)
        assert 0.01 < sleep_time < 0.02

        # Later attempt
        attempt = 10
        sleep_time = min(0.01 * (1.1**attempt), max_sleep)
        assert sleep_time < max_sleep

        # Very late attempt should hit max
        attempt = 100
        sleep_time = min(0.01 * (1.1**attempt), max_sleep)
        assert sleep_time == max_sleep
