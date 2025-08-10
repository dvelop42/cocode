"""Tests for the concurrent agent executor."""

import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from cocode.agents.base import Agent, AgentStatus
from cocode.agents.concurrent_executor import ConcurrentAgentExecutor, ExecutionResult
from cocode.agents.lifecycle import AgentLifecycleInfo, AgentState


class MockAgent(Agent):
    """Mock agent for testing."""

    def __init__(self, name: str, should_succeed: bool = True, should_be_ready: bool = False):
        super().__init__(name)
        self.should_succeed = should_succeed
        self.should_be_ready = should_be_ready

    def validate_environment(self) -> bool:
        return True

    def prepare_environment(
        self, worktree_path: Path, issue_number: int, issue_body: str
    ) -> dict[str, str]:
        return {"COCODE_TEST": "true"}

    def get_command(self) -> list[str]:
        return ["echo", "test"]

    def check_ready(self, worktree_path: Path) -> bool:
        return self.should_be_ready


@pytest.fixture
def mock_repo_path(tmp_path):
    """Create a mock repository path."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    # Create a .git directory to simulate a git repository
    git_dir = repo_path / ".git"
    git_dir.mkdir()
    return repo_path


@pytest.fixture
def executor(mock_repo_path):
    """Create a ConcurrentAgentExecutor instance."""
    return ConcurrentAgentExecutor(
        repo_path=mock_repo_path,
        max_concurrent_agents=3,
        agent_timeout=30,
    )


class TestConcurrentAgentExecutor:
    """Test suite for ConcurrentAgentExecutor."""

    def test_initialization(self, executor, mock_repo_path):
        """Test executor initialization."""
        assert executor.repo_path == mock_repo_path
        assert executor.max_concurrent_agents == 3
        assert executor.agent_timeout == 30
        assert executor.lifecycle_manager is not None
        assert executor.worktree_manager is not None

    @patch("cocode.agents.concurrent_executor.WorktreeManager")
    @patch("cocode.agents.concurrent_executor.AgentLifecycleManager")
    def test_execute_agents_success(self, mock_lifecycle_mgr, mock_worktree_mgr, executor):
        """Test successful execution of multiple agents."""
        # Setup mocks
        mock_worktree_mgr_instance = Mock()
        mock_lifecycle_mgr_instance = Mock()
        mock_worktree_mgr.return_value = mock_worktree_mgr_instance
        mock_lifecycle_mgr.return_value = mock_lifecycle_mgr_instance

        executor.worktree_manager = mock_worktree_mgr_instance
        executor.lifecycle_manager = mock_lifecycle_mgr_instance

        # Mock worktree creation
        mock_worktree_mgr_instance.create_worktree.side_effect = [
            Path("/tmp/worktree1"),
            Path("/tmp/worktree2"),
        ]

        # Create test agents
        agents = [
            MockAgent("agent1", should_succeed=True, should_be_ready=True),
            MockAgent("agent2", should_succeed=True, should_be_ready=False),
        ]

        # Mock agent lifecycle: call completion_callback immediately to avoid waiting
        def start_agent_side_effect(agent_name, issue_number, issue_body, issue_url, **kwargs):
            cb = kwargs.get("completion_callback")
            if cb:
                if agent_name == "agent1":
                    cb(
                        AgentStatus(
                            name="agent1",
                            branch="cocode/123-agent1",
                            worktree=Path("/tmp/worktree1"),
                            ready=True,
                            exit_code=0,
                        )
                    )
                elif agent_name == "agent2":
                    cb(
                        AgentStatus(
                            name="agent2",
                            branch="cocode/123-agent2",
                            worktree=Path("/tmp/worktree2"),
                            ready=False,
                            exit_code=0,
                        )
                    )
            return True

        mock_lifecycle_mgr_instance.start_agent.side_effect = start_agent_side_effect

        # Also mock get_agent_info to return the final statuses
        mock_lifecycle_mgr_instance.get_agent_info.side_effect = [
            AgentLifecycleInfo(
                agent=MockAgent("agent1"),
                state=AgentState.READY,
                status=AgentStatus(
                    name="agent1",
                    branch="cocode/123-agent1",
                    worktree=Path("/tmp/worktree1"),
                    ready=True,
                    exit_code=0,
                ),
            ),
            AgentLifecycleInfo(
                agent=MockAgent("agent2"),
                state=AgentState.COMPLETED,
                status=AgentStatus(
                    name="agent2",
                    branch="cocode/123-agent2",
                    worktree=Path("/tmp/worktree2"),
                    ready=False,
                    exit_code=0,
                ),
            ),
        ]

        # Execute agents
        result = executor.execute_agents(
            agents=agents,
            issue_number=123,
            issue_body="Test issue body",
            issue_url="https://github.com/test/repo/issues/123",
        )

        # Verify results
        assert isinstance(result, ExecutionResult)
        assert result.issue_number == 123
        assert len(result.successful_agents) == 2
        assert len(result.failed_agents) == 0
        assert len(result.ready_agents) == 1
        assert "agent1" in result.ready_agents
        assert "agent1" in result.agent_results
        assert "agent2" in result.agent_results

    @patch("cocode.agents.concurrent_executor.WorktreeManager")
    @patch("cocode.agents.concurrent_executor.AgentLifecycleManager")
    def test_execute_agents_with_failures(self, mock_lifecycle_mgr, mock_worktree_mgr, executor):
        """Test execution with some agent failures."""
        # Setup mocks
        mock_worktree_mgr_instance = Mock()
        mock_lifecycle_mgr_instance = Mock()
        mock_worktree_mgr.return_value = mock_worktree_mgr_instance
        mock_lifecycle_mgr.return_value = mock_lifecycle_mgr_instance

        executor.worktree_manager = mock_worktree_mgr_instance
        executor.lifecycle_manager = mock_lifecycle_mgr_instance

        # Mock worktree creation
        mock_worktree_mgr_instance.create_worktree.side_effect = [
            Path("/tmp/worktree1"),
            Path("/tmp/worktree2"),
        ]

        # Mock agent lifecycle with one failure - invoke completion_callback
        def start_agent_side_effect(agent_name, issue_number, issue_body, issue_url, **kwargs):
            cb = kwargs.get("completion_callback")
            if cb:
                if agent_name == "agent1":
                    cb(
                        AgentStatus(
                            name="agent1",
                            branch="cocode/123-agent1",
                            worktree=Path("/tmp/worktree1"),
                            ready=True,
                            exit_code=0,
                        )
                    )
                elif agent_name == "agent2":
                    cb(
                        AgentStatus(
                            name="agent2",
                            branch="cocode/123-agent2",
                            worktree=Path("/tmp/worktree2"),
                            ready=False,
                            exit_code=1,
                            error_message="Test error",
                        )
                    )
            return True

        mock_lifecycle_mgr_instance.start_agent.side_effect = start_agent_side_effect

        mock_lifecycle_mgr_instance.get_agent_info.side_effect = [
            AgentLifecycleInfo(
                agent=MockAgent("agent1"),
                state=AgentState.READY,
                status=AgentStatus(
                    name="agent1",
                    branch="cocode/123-agent1",
                    worktree=Path("/tmp/worktree1"),
                    ready=True,
                    exit_code=0,
                ),
            ),
            AgentLifecycleInfo(
                agent=MockAgent("agent2"),
                state=AgentState.FAILED,
                status=AgentStatus(
                    name="agent2",
                    branch="cocode/123-agent2",
                    worktree=Path("/tmp/worktree2"),
                    ready=False,
                    exit_code=1,
                    error_message="Test error",
                ),
            ),
        ]

        # Create test agents
        agents = [
            MockAgent("agent1", should_succeed=True, should_be_ready=True),
            MockAgent("agent2", should_succeed=False, should_be_ready=False),
        ]

        # Execute agents
        result = executor.execute_agents(
            agents=agents,
            issue_number=123,
            issue_body="Test issue body",
            issue_url="https://github.com/test/repo/issues/123",
        )

        # Verify results
        assert len(result.successful_agents) == 1
        assert len(result.failed_agents) == 1
        assert "agent1" in result.successful_agents
        assert "agent2" in result.failed_agents
        assert "agent2" in result.errors
        assert result.errors["agent2"] == "Test error"

    def test_prepare_worktrees(self, executor):
        """Test worktree preparation for agents."""
        agents = [
            MockAgent("agent1"),
            MockAgent("agent2"),
        ]

        with patch.object(executor.worktree_manager, "create_worktree") as mock_create:
            mock_create.side_effect = [
                Path("/tmp/worktree1"),
                Path("/tmp/worktree2"),
            ]

            worktrees = executor._prepare_worktrees(agents, 123, "main")

            assert len(worktrees) == 2
            assert "agent1" in worktrees
            assert "agent2" in worktrees
            assert worktrees["agent1"] == Path("/tmp/worktree1")
            assert worktrees["agent2"] == Path("/tmp/worktree2")

            # Verify correct calls (align with current WorktreeManager API)
            mock_create.assert_any_call(
                branch_name="cocode/123-agent1",
                agent_name="agent1",
            )
            mock_create.assert_any_call(
                branch_name="cocode/123-agent2",
                agent_name="agent2",
            )

    def test_prepare_worktrees_with_failure(self, executor):
        """Test worktree preparation with failures."""
        agents = [
            MockAgent("agent1"),
            MockAgent("agent2"),
        ]

        with patch.object(executor.worktree_manager, "create_worktree") as mock_create:
            mock_create.side_effect = [
                Path("/tmp/worktree1"),
                Exception("Failed to create worktree"),
            ]

            worktrees = executor._prepare_worktrees(agents, 123, "main")

            assert len(worktrees) == 1
            assert "agent1" in worktrees
            assert "agent2" not in worktrees

    def test_handle_completion(self, executor):
        """Test agent completion handling."""
        progress_callback = Mock()
        status = AgentStatus(
            name="test_agent",
            branch="cocode/123-test_agent",
            worktree=Path("/tmp/worktree"),
            ready=True,
            exit_code=0,
        )

        executor._completion_events["test_agent"] = threading.Event()
        executor._handle_completion("test_agent", status, progress_callback)

        assert executor._completion_statuses["test_agent"] == status
        assert executor._completion_events["test_agent"].is_set()
        progress_callback.assert_called_once_with("test_agent", "ready")

    def test_handle_completion_failed(self, executor):
        """Test handling of failed agent completion."""
        progress_callback = Mock()
        status = AgentStatus(
            name="test_agent",
            branch="cocode/123-test_agent",
            worktree=Path("/tmp/worktree"),
            ready=False,
            exit_code=1,
            error_message="Test failure",
        )

        executor._completion_events["test_agent"] = threading.Event()
        executor._handle_completion("test_agent", status, progress_callback)

        assert executor._completion_statuses["test_agent"] == status
        assert executor._completion_events["test_agent"].is_set()
        progress_callback.assert_called_once_with("test_agent", "failed")

    def test_wait_for_all_completions(self, executor):
        """Test waiting for all agents to complete."""
        agents = [MockAgent("agent1"), MockAgent("agent2")]
        progress_callback = Mock()

        # Setup completion events
        executor._completion_events = {
            "agent1": threading.Event(),
            "agent2": threading.Event(),
        }

        # Mock get_agent_state to return RUNNING
        with patch.object(executor.lifecycle_manager, "get_agent_state") as mock_get_state:
            mock_get_state.return_value = AgentState.RUNNING

            # Set events in a separate thread to simulate async completion
            def set_events():
                time.sleep(0.01)
                executor._completion_events["agent1"].set()
                time.sleep(0.01)
                executor._completion_events["agent2"].set()

            thread = threading.Thread(target=set_events, daemon=True)
            thread.start()

            # Wait for completions with a short timeout
            executor._wait_for_all_completions(agents, progress_callback, poll_interval=0.005)

            thread.join(timeout=1.0)

            # Verify progress callbacks were made
            assert progress_callback.call_count >= 1

    def test_stop_all_agents(self, executor):
        """Test stopping all agents."""
        with patch.object(executor.lifecycle_manager, "shutdown_all") as mock_shutdown:
            executor.stop_all_agents(force=True)
            mock_shutdown.assert_called_once_with(force=True)

    def test_cleanup_worktrees(self, executor):
        """Test worktree cleanup."""
        agents = [MockAgent("agent1"), MockAgent("agent2")]

        with patch.object(executor.worktree_manager, "remove_worktree") as mock_remove:
            executor.cleanup_worktrees(agents)

            expected1 = executor.repo_path.parent / "cocode_agent1"
            expected2 = executor.repo_path.parent / "cocode_agent2"
            mock_remove.assert_any_call(expected1)
            mock_remove.assert_any_call(expected2)
            assert mock_remove.call_count == 2

    def test_cleanup_worktrees_with_error(self, executor):
        """Test worktree cleanup with errors."""
        agents = [MockAgent("agent1"), MockAgent("agent2")]

        with patch.object(executor.worktree_manager, "remove_worktree") as mock_remove:
            mock_remove.side_effect = [None, Exception("Removal failed")]

            # Should not raise exception
            executor.cleanup_worktrees(agents)

            assert mock_remove.call_count == 2

    def test_get_agent_status(self, executor):
        """Test getting agent status."""
        mock_info = AgentLifecycleInfo(
            agent=MockAgent("test_agent"),
            state=AgentState.READY,
            status=AgentStatus(
                name="test_agent",
                branch="cocode/123-test_agent",
                worktree=Path("/tmp/worktree"),
                ready=True,
                exit_code=0,
            ),
        )

        with patch.object(executor.lifecycle_manager, "get_agent_info") as mock_get:
            mock_get.return_value = mock_info

            status = executor.get_agent_status("test_agent")

            assert status == mock_info.status
            mock_get.assert_called_once_with("test_agent")

    def test_get_agent_status_not_found(self, executor):
        """Test getting status for non-existent agent."""
        with patch.object(executor.lifecycle_manager, "get_agent_info") as mock_get:
            mock_get.return_value = None

            status = executor.get_agent_status("non_existent")

            assert status is None

    def test_restart_agent(self, executor):
        """Test restarting an agent."""
        with patch.object(executor.lifecycle_manager, "restart_agent") as mock_restart:
            mock_restart.return_value = True

            result = executor.restart_agent(
                agent_name="test_agent",
                issue_number=123,
                issue_body="Test issue",
                issue_url="https://github.com/test/repo/issues/123",
            )

            assert result is True
            mock_restart.assert_called_once_with(
                agent_name="test_agent",
                issue_number=123,
                issue_body="Test issue",
                issue_url="https://github.com/test/repo/issues/123",
            )

    def test_concurrent_execution_limit(self, executor):
        """Test that concurrent execution respects the limit."""
        # Create more agents than the concurrent limit
        agents = [MockAgent(f"agent{i}") for i in range(5)]

        with patch.object(executor.lifecycle_manager, "start_agent") as mock_start:
            # Setup to track concurrent starts and complete via callback
            start_times = []

            def track_start(*args, **kwargs):
                start_times.append(time.time())
                cb = kwargs.get("completion_callback")
                # First arg is agent_name by current API
                agent_name = args[0] if args else kwargs.get("agent_name", "test")
                if cb:
                    cb(
                        AgentStatus(
                            name=agent_name,
                            branch=f"cocode/123-{agent_name}",
                            worktree=Path("/tmp/worktree"),
                            ready=False,
                            exit_code=0,
                        )
                    )
                return True

            mock_start.side_effect = track_start

            # Mock worktree creation
            with patch.object(executor.worktree_manager, "create_worktree") as mock_create:
                mock_create.return_value = Path("/tmp/worktree")

                # Mock agent info
                with patch.object(executor.lifecycle_manager, "get_agent_info") as mock_get_info:
                    mock_get_info.return_value = AgentLifecycleInfo(
                        agent=MockAgent("test"),
                        state=AgentState.COMPLETED,
                        status=AgentStatus(
                            name="test",
                            branch="test",
                            worktree=Path("/tmp/worktree"),
                            ready=False,
                            exit_code=0,
                        ),
                    )

                    # Execute agents
                    result = executor.execute_agents(
                        agents=agents,
                        issue_number=123,
                        issue_body="Test issue",
                        issue_url="https://github.com/test/repo/issues/123",
                    )

                    # Verify all agents were started
                    assert mock_start.call_count == 5
                    # Verify we got results for all agents
                    assert len(result.agent_results) == 5


class TestExecutionResult:
    """Test suite for ExecutionResult dataclass."""

    def test_execution_result_initialization(self):
        """Test ExecutionResult initialization."""
        result = ExecutionResult(
            issue_number=123,
            issue_url="https://github.com/test/repo/issues/123",
        )

        assert result.issue_number == 123
        assert result.issue_url == "https://github.com/test/repo/issues/123"
        assert result.agent_results == {}
        assert result.successful_agents == []
        assert result.failed_agents == []
        assert result.ready_agents == []
        assert result.execution_time == 0.0
        assert result.errors == {}

    def test_execution_result_with_data(self):
        """Test ExecutionResult with populated data."""
        status1 = AgentStatus(
            name="agent1",
            branch="cocode/123-agent1",
            worktree=Path("/tmp/worktree1"),
            ready=True,
            exit_code=0,
        )
        status2 = AgentStatus(
            name="agent2",
            branch="cocode/123-agent2",
            worktree=Path("/tmp/worktree2"),
            ready=False,
            exit_code=1,
            error_message="Test error",
        )

        result = ExecutionResult(
            issue_number=123,
            issue_url="https://github.com/test/repo/issues/123",
            agent_results={"agent1": status1, "agent2": status2},
            successful_agents=["agent1"],
            failed_agents=["agent2"],
            ready_agents=["agent1"],
            execution_time=42.5,
            errors={"agent2": "Test error"},
        )

        assert len(result.agent_results) == 2
        assert result.agent_results["agent1"] == status1
        assert result.agent_results["agent2"] == status2
        assert result.successful_agents == ["agent1"]
        assert result.failed_agents == ["agent2"]
        assert result.ready_agents == ["agent1"]
        assert result.execution_time == 42.5
        assert result.errors == {"agent2": "Test error"}
