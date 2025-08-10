"""Simple unit tests for concurrent executor without complex mocking."""

from pathlib import Path
from unittest.mock import Mock, patch

from cocode.agents.base import Agent, AgentStatus
from cocode.agents.concurrent_executor import ConcurrentAgentExecutor, ExecutionResult


class SimpleAgent(Agent):
    """Simple test agent."""

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


class TestConcurrentExecutorSimple:
    """Simple tests for ConcurrentAgentExecutor."""

    @patch("cocode.agents.concurrent_executor.WorktreeManager")
    @patch("cocode.agents.concurrent_executor.AgentLifecycleManager")
    def test_basic_functionality(self, mock_lifecycle_class, mock_worktree_class):
        """Test basic concurrent executor functionality."""
        # Setup mocks
        mock_worktree = Mock()
        mock_lifecycle = Mock()
        mock_worktree_class.return_value = mock_worktree
        mock_lifecycle_class.return_value = mock_lifecycle

        # Create executor
        repo_path = Path("/tmp/test_repo")
        executor = ConcurrentAgentExecutor(
            repo_path=repo_path,
            max_concurrent_agents=3,
            agent_timeout=30,
        )

        # Verify initialization
        assert executor.repo_path == repo_path
        assert executor.max_concurrent_agents == 3
        assert executor.agent_timeout == 30
        mock_lifecycle_class.assert_called_once_with(
            max_concurrent_agents=3,
            default_timeout=30,
        )

    def test_execution_result_structure(self):
        """Test ExecutionResult data structure."""
        result = ExecutionResult(
            issue_number=123,
            issue_url="https://github.com/test/repo/issues/123",
        )

        # Add some test data
        status1 = AgentStatus(
            name="agent1",
            branch="test",
            worktree=Path("/tmp/worktree1"),
            ready=True,
            exit_code=0,
        )

        result.agent_results["agent1"] = status1
        result.successful_agents.append("agent1")
        result.ready_agents.append("agent1")
        result.execution_time = 1.5

        # Verify structure
        assert result.issue_number == 123
        assert "agent1" in result.agent_results
        assert "agent1" in result.successful_agents
        assert "agent1" in result.ready_agents
        assert len(result.failed_agents) == 0
        assert result.execution_time == 1.5

    @patch("cocode.agents.concurrent_executor.WorktreeManager")
    def test_worktree_preparation(self, mock_worktree_class):
        """Test worktree preparation logic."""
        mock_worktree = Mock()
        mock_worktree_class.return_value = mock_worktree

        # Setup worktree creation to return paths
        mock_worktree.create_worktree.side_effect = [
            Path("/tmp/worktree1"),
            Path("/tmp/worktree2"),
        ]

        with patch("cocode.agents.concurrent_executor.AgentLifecycleManager"):
            executor = ConcurrentAgentExecutor(
                repo_path=Path("/tmp/repo"),
                max_concurrent_agents=2,
            )

            agents = [
                SimpleAgent("agent1"),
                SimpleAgent("agent2"),
            ]

            # Test worktree preparation
            worktrees = executor._prepare_worktrees(agents, 123, "main")

            # Verify worktrees were created
            assert len(worktrees) == 2
            assert worktrees["agent1"] == Path("/tmp/worktree1")
            assert worktrees["agent2"] == Path("/tmp/worktree2")

            # Verify correct calls to create_worktree
            calls = mock_worktree.create_worktree.call_args_list
            assert len(calls) == 2
            assert calls[0].kwargs == {"branch_name": "cocode/123-agent1", "agent_name": "agent1"}
            assert calls[1].kwargs == {"branch_name": "cocode/123-agent2", "agent_name": "agent2"}

    @patch("cocode.agents.concurrent_executor.WorktreeManager")
    @patch("cocode.agents.concurrent_executor.AgentLifecycleManager")
    def test_agent_registration(self, mock_lifecycle_class, mock_worktree_class):
        """Test that agents are properly registered with lifecycle manager."""
        mock_worktree = Mock()
        mock_lifecycle = Mock()
        mock_worktree_class.return_value = mock_worktree
        mock_lifecycle_class.return_value = mock_lifecycle

        # Setup successful worktree creation
        mock_worktree.create_worktree.return_value = Path("/tmp/worktree")

        # Setup lifecycle manager to succeed and immediately invoke completion callback
        def start_agent_side_effect(agent_name, issue_number, issue_body, issue_url, **kwargs):
            cb = kwargs.get("completion_callback")
            if cb:
                cb(
                    AgentStatus(
                        name=agent_name,
                        branch=f"cocode/{issue_number}-{agent_name}",
                        worktree=Path("/tmp/worktree"),
                        ready=True,
                        exit_code=0,
                    )
                )
            return True

        mock_lifecycle.start_agent.side_effect = start_agent_side_effect
        mock_lifecycle.get_agent_info.return_value = None

        executor = ConcurrentAgentExecutor(
            repo_path=Path("/tmp/repo"),
            max_concurrent_agents=2,
        )

        agents = [SimpleAgent("test_agent")]

        # Execute agents (will complete via callback)
        executor.execute_agents(
            agents=agents,
            issue_number=456,
            issue_body="Test issue",
            issue_url="https://github.com/test/repo/issues/456",
        )

        # Verify agent was registered
        mock_lifecycle.register_agent.assert_called_once()
        call_args = mock_lifecycle.register_agent.call_args
        assert call_args.kwargs["agent"].name == "test_agent"
        assert call_args.kwargs["worktree_path"] == Path("/tmp/worktree")
        assert call_args.kwargs["max_restarts"] == 0

    @patch("cocode.agents.concurrent_executor.WorktreeManager")
    @patch("cocode.agents.concurrent_executor.AgentLifecycleManager")
    def test_cleanup_worktrees(self, mock_lifecycle_class, mock_worktree_class):
        """Test worktree cleanup."""
        mock_worktree = Mock()
        mock_lifecycle = Mock()
        mock_worktree_class.return_value = mock_worktree
        mock_lifecycle_class.return_value = mock_lifecycle

        executor = ConcurrentAgentExecutor(
            repo_path=Path("/tmp/repo"),
            max_concurrent_agents=2,
        )

        agents = [
            SimpleAgent("agent1"),
            SimpleAgent("agent2"),
        ]

        # Test cleanup
        executor.cleanup_worktrees(agents)

        # Verify remove_worktree was called for each agent
        calls = mock_worktree.remove_worktree.call_args_list
        assert len(calls) == 2
        assert calls[0][0][0] == Path("/tmp/cocode_agent1")
        assert calls[1][0][0] == Path("/tmp/cocode_agent2")
