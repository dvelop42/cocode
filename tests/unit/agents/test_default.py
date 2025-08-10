"""Tests for default agent implementations."""

from pathlib import Path
from unittest.mock import patch

from cocode.agents.default import GitBasedAgent


class TestGitBasedAgent:
    """Test the GitBasedAgent class."""

    def test_check_ready_calls_check_ready_in_worktree(self, tmp_path: Path):
        """Test that check_ready uses the ready watcher."""

        class ConcreteAgent(GitBasedAgent):
            """Concrete implementation for testing."""

            def validate_environment(self) -> bool:
                return True

            def prepare_environment(
                self, worktree_path: Path, issue_number: int, issue_body: str
            ) -> dict[str, str]:
                return {}

            def get_command(self) -> list[str]:
                return ["echo", "test"]

        agent = ConcreteAgent("test-agent")

        with patch("cocode.agents.default.check_ready_in_worktree") as mock_check:
            mock_check.return_value = True

            result = agent.check_ready(tmp_path)

            assert result is True
            mock_check.assert_called_once_with(tmp_path, "cocode ready for check")

    def test_check_ready_returns_false_when_not_ready(self, tmp_path: Path):
        """Test that check_ready returns False when marker not found."""

        class ConcreteAgent(GitBasedAgent):
            """Concrete implementation for testing."""

            def validate_environment(self) -> bool:
                return True

            def prepare_environment(
                self, worktree_path: Path, issue_number: int, issue_body: str
            ) -> dict[str, str]:
                return {}

            def get_command(self) -> list[str]:
                return ["echo", "test"]

        agent = ConcreteAgent("test-agent")

        with patch("cocode.agents.default.check_ready_in_worktree") as mock_check:
            mock_check.return_value = False

            result = agent.check_ready(tmp_path)

            assert result is False
            mock_check.assert_called_once_with(tmp_path, "cocode ready for check")

    def test_validate_environment_default_true(self):
        """Default validate_environment returns True."""

        agent = GitBasedAgent("demo")
        assert agent.validate_environment() is True

    def test_prepare_environment_default_empty(self, tmp_path: Path):
        """Default prepare_environment returns empty mapping."""

        agent = GitBasedAgent("demo")
        env = agent.prepare_environment(tmp_path, 123, "body")
        assert env == {}

    def test_get_command_default_message(self):
        """Default get_command returns informative message with name."""

        name = "demo-agent"
        agent = GitBasedAgent(name)
        cmd = agent.get_command()
        assert cmd[:2] == ["echo", f"Agent {name} not implemented"]
