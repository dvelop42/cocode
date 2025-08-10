"""Tests for agent lifecycle manager."""

import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from cocode.agents.base import Agent, AgentStatus
from cocode.agents.lifecycle import AgentLifecycleManager, AgentState


class MockAgent(Agent):
    """Mock agent for testing."""

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


@pytest.fixture
def lifecycle_manager():
    """Create a lifecycle manager for testing."""
    return AgentLifecycleManager(max_concurrent_agents=3, default_timeout=10)


@pytest.fixture
def mock_agent():
    """Create a mock agent."""
    return MockAgent("test-agent")


@pytest.fixture
def mock_runner(lifecycle_manager):
    """Mock the agent runner."""
    with patch.object(lifecycle_manager, "runner") as mock:
        yield mock


class TestAgentLifecycleManager:
    """Test the agent lifecycle manager."""

    def test_register_agent(self, lifecycle_manager, mock_agent):
        """Test registering an agent."""
        worktree_path = Path("/tmp/test")
        lifecycle_manager.register_agent(mock_agent, worktree_path, max_restarts=2)

        assert "test-agent" in lifecycle_manager.agents
        info = lifecycle_manager.agents["test-agent"]
        assert info.agent == mock_agent
        assert info.worktree_path == worktree_path
        assert info.max_restarts == 2
        assert info.state == AgentState.IDLE

    def test_register_duplicate_agent(self, lifecycle_manager, mock_agent):
        """Test registering a duplicate agent updates it."""
        worktree_path1 = Path("/tmp/test1")
        worktree_path2 = Path("/tmp/test2")

        lifecycle_manager.register_agent(mock_agent, worktree_path1)
        lifecycle_manager.register_agent(mock_agent, worktree_path2)

        assert lifecycle_manager.agents["test-agent"].worktree_path == worktree_path2

    def test_get_agent_state(self, lifecycle_manager, mock_agent):
        """Test getting agent state."""
        worktree_path = Path("/tmp/test")
        lifecycle_manager.register_agent(mock_agent, worktree_path)

        state = lifecycle_manager.get_agent_state("test-agent")
        assert state == AgentState.IDLE

        state = lifecycle_manager.get_agent_state("nonexistent")
        assert state is None

    def test_get_agent_info(self, lifecycle_manager, mock_agent):
        """Test getting agent info."""
        worktree_path = Path("/tmp/test")
        lifecycle_manager.register_agent(mock_agent, worktree_path)

        info = lifecycle_manager.get_agent_info("test-agent")
        assert info is not None
        assert info.agent == mock_agent

        info = lifecycle_manager.get_agent_info("nonexistent")
        assert info is None

    def test_get_all_agents(self, lifecycle_manager):
        """Test getting all agents."""
        agent1 = MockAgent("agent1")
        agent2 = MockAgent("agent2")

        lifecycle_manager.register_agent(agent1, Path("/tmp/1"))
        lifecycle_manager.register_agent(agent2, Path("/tmp/2"))

        all_agents = lifecycle_manager.get_all_agents()
        assert len(all_agents) == 2
        assert "agent1" in all_agents
        assert "agent2" in all_agents

    @patch("cocode.agents.lifecycle.threading.Thread")
    def test_start_agent(self, mock_thread_class, lifecycle_manager, mock_agent):
        """Test starting an agent."""
        mock_thread = Mock()
        mock_thread_class.return_value = mock_thread

        worktree_path = Path("/tmp/test")
        lifecycle_manager.register_agent(mock_agent, worktree_path)

        result = lifecycle_manager.start_agent(
            "test-agent",
            issue_number=123,
            issue_body="Test issue",
            issue_url="https://github.com/test/repo/issues/123",
        )

        assert result is True
        assert lifecycle_manager.agents["test-agent"].state == AgentState.STARTING
        mock_thread.start.assert_called_once()

    def test_start_unregistered_agent(self, lifecycle_manager):
        """Test starting an unregistered agent fails."""
        result = lifecycle_manager.start_agent(
            "nonexistent",
            issue_number=123,
            issue_body="Test",
            issue_url="https://test.com",
        )
        assert result is False

    def test_start_already_running_agent(self, lifecycle_manager, mock_agent):
        """Test starting an already running agent fails."""
        worktree_path = Path("/tmp/test")
        lifecycle_manager.register_agent(mock_agent, worktree_path)

        # Manually set state to running
        lifecycle_manager.agents["test-agent"].state = AgentState.RUNNING

        result = lifecycle_manager.start_agent(
            "test-agent",
            issue_number=123,
            issue_body="Test",
            issue_url="https://test.com",
        )
        assert result is False

    @patch("cocode.agents.lifecycle.threading.Thread")
    def test_concurrent_limit(self, mock_thread_class, lifecycle_manager):
        """Test concurrent agent limit is enforced."""
        mock_thread = Mock()
        mock_thread_class.return_value = mock_thread

        # Register 4 agents (limit is 3)
        for i in range(4):
            agent = MockAgent(f"agent{i}")
            lifecycle_manager.register_agent(agent, Path(f"/tmp/{i}"))

        # Start 3 agents (should succeed)
        for i in range(3):
            lifecycle_manager._running_count = i  # Simulate running count
            result = lifecycle_manager.start_agent(
                f"agent{i}",
                issue_number=123,
                issue_body="Test",
                issue_url="https://test.com",
            )
            assert result is True

        # Try to start 4th agent (should fail due to limit)
        lifecycle_manager._running_count = 3
        result = lifecycle_manager.start_agent(
            "agent3",
            issue_number=123,
            issue_body="Test",
            issue_url="https://test.com",
        )
        assert result is False

    def test_stop_agent(self, lifecycle_manager, mock_agent):
        """Test stopping an agent."""
        worktree_path = Path("/tmp/test")
        lifecycle_manager.register_agent(mock_agent, worktree_path)

        # Set to running state
        lifecycle_manager.agents["test-agent"].state = AgentState.RUNNING

        result = lifecycle_manager.stop_agent("test-agent")
        assert result is True
        assert lifecycle_manager.agents["test-agent"].state == AgentState.STOPPED

    def test_stop_non_running_agent(self, lifecycle_manager, mock_agent):
        """Test stopping a non-running agent fails."""
        worktree_path = Path("/tmp/test")
        lifecycle_manager.register_agent(mock_agent, worktree_path)

        result = lifecycle_manager.stop_agent("test-agent")
        assert result is False

    @patch("cocode.agents.lifecycle.threading.Thread")
    def test_restart_agent(self, mock_thread_class, lifecycle_manager, mock_agent):
        """Test restarting an agent."""
        mock_thread = Mock()
        mock_thread_class.return_value = mock_thread

        worktree_path = Path("/tmp/test")
        lifecycle_manager.register_agent(mock_agent, worktree_path)

        result = lifecycle_manager.restart_agent(
            "test-agent",
            issue_number=123,
            issue_body="Test",
            issue_url="https://test.com",
        )

        assert result is True
        assert lifecycle_manager.agents["test-agent"].restart_count == 1

    def test_restart_limit(self, lifecycle_manager, mock_agent):
        """Test restart limit is enforced."""
        worktree_path = Path("/tmp/test")
        lifecycle_manager.register_agent(mock_agent, worktree_path, max_restarts=2)

        # Set restart count to max
        lifecycle_manager.agents["test-agent"].restart_count = 2

        result = lifecycle_manager.restart_agent(
            "test-agent",
            issue_number=123,
            issue_body="Test",
            issue_url="https://test.com",
        )

        assert result is False

    def test_reset_agent(self, lifecycle_manager, mock_agent):
        """Test resetting an agent."""
        worktree_path = Path("/tmp/test")
        lifecycle_manager.register_agent(mock_agent, worktree_path)

        # Set some state
        info = lifecycle_manager.agents["test-agent"]
        info.state = AgentState.FAILED
        info.error = "Test error"
        info.restart_count = 2
        info.output_lines = ["line1", "line2"]

        result = lifecycle_manager.reset_agent("test-agent")
        assert result is True

        # Check reset
        assert info.state == AgentState.IDLE
        assert info.error is None
        assert info.restart_count == 0
        assert len(info.output_lines) == 0

    def test_reset_running_agent(self, lifecycle_manager, mock_agent):
        """Test resetting a running agent fails."""
        worktree_path = Path("/tmp/test")
        lifecycle_manager.register_agent(mock_agent, worktree_path)

        lifecycle_manager.agents["test-agent"].state = AgentState.RUNNING

        result = lifecycle_manager.reset_agent("test-agent")
        assert result is False

    def test_is_any_running(self, lifecycle_manager):
        """Test checking if any agents are running."""
        agent1 = MockAgent("agent1")
        agent2 = MockAgent("agent2")

        lifecycle_manager.register_agent(agent1, Path("/tmp/1"))
        lifecycle_manager.register_agent(agent2, Path("/tmp/2"))

        assert lifecycle_manager.is_any_running() is False

        lifecycle_manager.agents["agent1"].state = AgentState.RUNNING
        assert lifecycle_manager.is_any_running() is True

        lifecycle_manager.agents["agent1"].state = AgentState.COMPLETED
        assert lifecycle_manager.is_any_running() is False

    def test_wait_for_completion_success(self, lifecycle_manager, mock_agent):
        """Test waiting for completion succeeds."""
        worktree_path = Path("/tmp/test")
        lifecycle_manager.register_agent(mock_agent, worktree_path)

        lifecycle_manager.agents["test-agent"].state = AgentState.RUNNING

        # Simulate completion in another thread
        def complete_agent():
            time.sleep(0.1)
            lifecycle_manager.agents["test-agent"].state = AgentState.COMPLETED

        thread = threading.Thread(target=complete_agent)
        thread.start()

        result = lifecycle_manager.wait_for_completion(timeout=1)
        thread.join()

        assert result is True

    def test_wait_for_completion_timeout(self, lifecycle_manager, mock_agent):
        """Test waiting for completion times out."""
        worktree_path = Path("/tmp/test")
        lifecycle_manager.register_agent(mock_agent, worktree_path)

        lifecycle_manager.agents["test-agent"].state = AgentState.RUNNING

        result = lifecycle_manager.wait_for_completion(timeout=0.1)
        assert result is False

    def test_shutdown_all(self, lifecycle_manager):
        """Test shutting down all agents."""
        agent1 = MockAgent("agent1")
        agent2 = MockAgent("agent2")

        lifecycle_manager.register_agent(agent1, Path("/tmp/1"))
        lifecycle_manager.register_agent(agent2, Path("/tmp/2"))

        lifecycle_manager.agents["agent1"].state = AgentState.RUNNING
        lifecycle_manager.agents["agent2"].state = AgentState.RUNNING

        with patch.object(lifecycle_manager, "stop_agent") as mock_stop:
            lifecycle_manager.shutdown_all()

            assert mock_stop.call_count == 2
            mock_stop.assert_any_call("agent1", force=False)
            mock_stop.assert_any_call("agent2", force=False)

    def test_run_agent_success(self, lifecycle_manager, mock_agent, mock_runner):
        """Test running an agent successfully."""
        worktree_path = Path("/tmp/test")
        lifecycle_manager.register_agent(mock_agent, worktree_path)

        # Mock successful status
        mock_status = AgentStatus(
            name="test-agent",
            branch="test-branch",
            worktree=worktree_path,
            ready=True,
            exit_code=0,
        )
        mock_runner.run_agent.return_value = mock_status

        # Callback to capture completion
        completion_called = False
        completion_status = None

        def on_completion(status):
            nonlocal completion_called, completion_status
            completion_called = True
            completion_status = status

        # Run agent
        lifecycle_manager._run_agent(
            "test-agent",
            issue_number=123,
            issue_body="Test",
            issue_url="https://test.com",
            stdout_callback=None,
            stderr_callback=None,
            completion_callback=on_completion,
        )

        # Check results
        info = lifecycle_manager.agents["test-agent"]
        assert info.state == AgentState.READY
        assert info.status == mock_status
        assert completion_called
        assert completion_status == mock_status

    def test_run_agent_failure(self, lifecycle_manager, mock_agent, mock_runner):
        """Test running an agent that fails."""
        worktree_path = Path("/tmp/test")
        lifecycle_manager.register_agent(mock_agent, worktree_path)

        # Mock failed status
        mock_status = AgentStatus(
            name="test-agent",
            branch="test-branch",
            worktree=worktree_path,
            ready=False,
            exit_code=1,
            error_message="Test error",
        )
        mock_runner.run_agent.return_value = mock_status

        # Run agent
        lifecycle_manager._run_agent(
            "test-agent",
            issue_number=123,
            issue_body="Test",
            issue_url="https://test.com",
            stdout_callback=None,
            stderr_callback=None,
            completion_callback=None,
        )

        # Check results
        info = lifecycle_manager.agents["test-agent"]
        assert info.state == AgentState.FAILED
        assert info.error == "Test error"

    def test_run_agent_exception(self, lifecycle_manager, mock_agent, mock_runner):
        """Test handling exception during agent run."""
        worktree_path = Path("/tmp/test")
        lifecycle_manager.register_agent(mock_agent, worktree_path)

        # Mock exception
        mock_runner.run_agent.side_effect = Exception("Test exception")

        # Run agent
        lifecycle_manager._run_agent(
            "test-agent",
            issue_number=123,
            issue_body="Test",
            issue_url="https://test.com",
            stdout_callback=None,
            stderr_callback=None,
            completion_callback=None,
        )

        # Check results
        info = lifecycle_manager.agents["test-agent"]
        assert info.state == AgentState.FAILED
        assert "Test exception" in info.error
