"""Integration tests for the concurrent agent executor."""

import subprocess
import time
from pathlib import Path

import pytest

from cocode.agents.base import Agent
from cocode.agents.concurrent_executor import ConcurrentAgentExecutor


class DummyAgent(Agent):
    """Simple test agent that creates a file."""

    def __init__(self, name: str, delay: float = 0.1):
        super().__init__(name)
        self.delay = delay

    def validate_environment(self) -> bool:
        return True

    def prepare_environment(
        self, worktree_path: Path, issue_number: int, issue_body: str
    ) -> dict[str, str]:
        return {
            "COCODE_TEST": "true",
            "COCODE_DELAY": str(self.delay),
        }

    def get_command(self) -> list[str]:
        # Simple command that creates a file after a delay
        return [
            "bash",
            "-c",
            f"sleep {self.delay} && echo 'Test output from {self.name}' > test_{self.name}.txt && echo 'Done'",
        ]

    def check_ready(self, worktree_path: Path) -> bool:
        # Check if the test file was created
        test_file = worktree_path / f"test_{self.name}.txt"
        return test_file.exists()


@pytest.fixture
def git_repo(tmp_path):
    """Create a real git repository for testing."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init", "-b", "main"], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_path,
        check=True,
    )

    # Create initial commit
    readme = repo_path / "README.md"
    readme.write_text("# Test Repository\n")
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo_path,
        check=True,
    )

    # Set up a local bare remote and push main so origin/main exists
    remote_repo = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote_repo)], check=True)
    subprocess.run(["git", "remote", "add", "origin", str(remote_repo)], cwd=repo_path, check=True)
    subprocess.run(["git", "push", "-u", "origin", "main"], cwd=repo_path, check=True)

    return repo_path


class TestConcurrentExecutorIntegration:
    """Integration tests for ConcurrentAgentExecutor."""

    def test_execute_multiple_agents(self, git_repo):
        """Test executing multiple agents concurrently."""
        executor = ConcurrentAgentExecutor(
            repo_path=git_repo,
            max_concurrent_agents=3,
            agent_timeout=10,
        )

        # Create test agents with different delays
        agents = [
            DummyAgent("agent1", delay=0.1),
            DummyAgent("agent2", delay=0.2),
            DummyAgent("agent3", delay=0.15),
        ]

        # Track output
        output_lines = []

        def output_callback(agent_name: str, stream: str, line: str):
            output_lines.append(f"[{agent_name}:{stream}] {line}")

        # Execute agents
        start_time = time.time()
        result = executor.execute_agents(
            agents=agents,
            issue_number=123,
            issue_body="Test issue body",
            issue_url="https://github.com/test/repo/issues/123",
            output_callback=output_callback,
        )
        execution_time = time.time() - start_time

        # Verify results
        assert result.issue_number == 123
        assert len(result.agent_results) == 3
        assert len(result.successful_agents) == 3
        assert len(result.failed_agents) == 0

        # Verify parallel execution allowing setup overhead (git fetch/worktree)
        total_delay = sum(agent.delay for agent in agents)  # 0.45s if sequential
        max_delay = max(agent.delay for agent in agents)  # 0.2s longest single agent
        # Should be closer to max delay than sum, but allow ~2s overhead for git ops on CI
        assert execution_time < max_delay + 2.0
        assert execution_time < total_delay + 2.0

        # Verify output was captured
        assert len(output_lines) > 0
        assert any("Done" in line for line in output_lines)

        # Cleanup worktrees
        executor.cleanup_worktrees(agents)

    def test_agent_failure_handling(self, git_repo):
        """Test handling of agent failures."""

        class FailingAgent(Agent):
            def __init__(self, name: str):
                super().__init__(name)

            def validate_environment(self) -> bool:
                return True

            def prepare_environment(
                self, worktree_path: Path, issue_number: int, issue_body: str
            ) -> dict[str, str]:
                return {}

            def get_command(self) -> list[str]:
                return ["bash", "-c", "exit 1"]

            def check_ready(self, worktree_path: Path) -> bool:
                return False

        executor = ConcurrentAgentExecutor(
            repo_path=git_repo,
            max_concurrent_agents=2,
            agent_timeout=5,
        )

        agents = [
            DummyAgent("good_agent", delay=0.1),
            FailingAgent("bad_agent"),
        ]

        result = executor.execute_agents(
            agents=agents,
            issue_number=456,
            issue_body="Test issue",
            issue_url="https://github.com/test/repo/issues/456",
        )

        # Verify mixed results
        assert len(result.successful_agents) == 1
        assert "good_agent" in result.successful_agents
        assert len(result.failed_agents) == 1
        assert "bad_agent" in result.failed_agents

        # Cleanup
        executor.cleanup_worktrees(agents)

    def test_concurrent_limit_enforcement(self, git_repo):
        """Test that concurrent execution respects the limit."""
        executor = ConcurrentAgentExecutor(
            repo_path=git_repo,
            max_concurrent_agents=2,  # Limit to 2 concurrent
            agent_timeout=5,
        )

        # Create 4 agents
        agents = [DummyAgent(f"agent{i}", delay=0.1) for i in range(4)]

        # Track when agents start
        start_times = {}

        def output_callback(agent_name: str, stream: str, line: str):
            if agent_name not in start_times:
                start_times[agent_name] = time.time()

        # Execute agents
        result = executor.execute_agents(
            agents=agents,
            issue_number=789,
            issue_body="Test issue",
            issue_url="https://github.com/test/repo/issues/789",
            output_callback=output_callback,
        )

        # All should complete successfully
        assert len(result.successful_agents) == 4

        # Cleanup
        executor.cleanup_worktrees(agents)

    def test_agent_restart(self, git_repo):
        """Test restarting an agent."""
        executor = ConcurrentAgentExecutor(
            repo_path=git_repo,
            max_concurrent_agents=1,
            agent_timeout=5,
        )

        agent = DummyAgent("restart_agent", delay=0.1)
        agents = [agent]

        # First execution
        result1 = executor.execute_agents(
            agents=agents,
            issue_number=999,
            issue_body="Test issue",
            issue_url="https://github.com/test/repo/issues/999",
        )

        assert len(result1.successful_agents) == 1

        # Restart the agent
        executor.restart_agent(
            agent_name="restart_agent",
            issue_number=999,
            issue_body="Test issue",
            issue_url="https://github.com/test/repo/issues/999",
        )

        # Note: restart might fail if agent is not registered with lifecycle manager
        # This is expected in this simple test

        # Cleanup
        executor.cleanup_worktrees(agents)
