"""Unit tests for git worktree manager - focused on security and validation."""

import re
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from cocode.git.worktree import WorktreeError, WorktreeManager


@pytest.fixture
def temp_repo(tmp_path):
    """Create a temporary git repository for testing."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()  # Just create .git dir for validation
    return repo_path


@pytest.fixture
def worktree_manager(temp_repo):
    """Create a WorktreeManager instance with a temporary repo."""
    return WorktreeManager(temp_repo)


class TestWorktreeManagerSecurity:
    """Test WorktreeManager security features."""

    def test_init_valid_repo(self, temp_repo):
        """Test initialization with valid git repository."""
        manager = WorktreeManager(temp_repo)
        assert manager.repo_path == temp_repo.resolve()

    def test_init_invalid_repo(self, tmp_path):
        """Test initialization with non-git directory."""
        non_git_dir = tmp_path / "not_a_repo"
        non_git_dir.mkdir()

        with pytest.raises(WorktreeError, match="Not a git repository"):
            WorktreeManager(non_git_dir)

    def test_validate_worktree_path_valid(self, worktree_manager):
        """Test path validation with valid path."""
        valid_path = worktree_manager.repo_path.parent / "cocode_test"
        assert worktree_manager._validate_worktree_path(valid_path) is True

    def test_validate_worktree_path_invalid(self, worktree_manager):
        """Test path validation with path outside allowed boundaries."""
        # Path in different directory
        invalid_path = Path("/tmp/evil/path")
        assert worktree_manager._validate_worktree_path(invalid_path) is False

        # Path with traversal
        invalid_path = worktree_manager.repo_path.parent.parent / "evil"
        assert worktree_manager._validate_worktree_path(invalid_path) is False

    def test_validate_agent_name_valid(self, worktree_manager):
        """Test agent name validation with valid names."""
        valid_names = [
            "agent-123",
            "test_agent",
            "MyAgent",
            "agent123",
            "a-b_c",
        ]

        for name in valid_names:
            result = worktree_manager._validate_agent_name(name)
            assert re.match(r"^[a-zA-Z0-9_-]+$", result)

    def test_validate_agent_name_empty(self, worktree_manager):
        """Test agent name validation with empty name."""
        with pytest.raises(WorktreeError, match="Agent name cannot be empty"):
            worktree_manager._validate_agent_name("")

    def test_validate_agent_name_path_traversal(self, worktree_manager):
        """Test agent name validation with path traversal attempts."""
        malicious_names = [
            "../evil",
            "../../etc/passwd",
            "test/../../../evil",
            "test\\..\\evil",
            "test/evil",
            "test\\evil",
        ]

        for name in malicious_names:
            with pytest.raises(WorktreeError, match="contains path separators"):
                worktree_manager._validate_agent_name(name)

    def test_validate_agent_name_sanitization(self, worktree_manager):
        """Test agent name sanitization of special characters."""
        test_cases = [
            ("agent@123", "agent_123"),
            ("test#agent", "test_agent"),
            ("my.agent", "my_agent"),
            ("agent!@#$%", "agent_____"),
            ("test agent", "test_agent"),
        ]

        for input_name, expected in test_cases:
            result = worktree_manager._validate_agent_name(input_name)
            assert result == expected

    @patch("cocode.git.worktree.subprocess.run")
    def test_run_git_command_success(self, mock_run, worktree_manager):
        """Test successful git command execution."""
        mock_run.return_value = Mock(
            stdout="command output",
            stderr="",
            returncode=0,
        )

        result = worktree_manager._run_git_command(["status"])

        mock_run.assert_called_once()
        assert result == "command output"

    @patch("cocode.git.worktree.subprocess.run")
    def test_run_git_command_failure(self, mock_run, worktree_manager):
        """Test git command execution failure."""
        mock_run.side_effect = subprocess.CalledProcessError(
            1, ["git", "status"], stderr="error message"
        )

        with pytest.raises(WorktreeError, match="Git command failed"):
            worktree_manager._run_git_command(["status"])

    @patch("cocode.git.worktree.subprocess.run")
    def test_run_git_command_git_not_found(self, mock_run, worktree_manager):
        """Test git command when git is not installed."""
        mock_run.side_effect = FileNotFoundError()

        with pytest.raises(WorktreeError, match="Git is not installed"):
            worktree_manager._run_git_command(["status"])

    def test_create_worktree_path_traversal_blocked(self, worktree_manager):
        """Test that path traversal in agent name is blocked."""
        branch_name = "test-branch"
        agent_name = "../../../evil"

        with pytest.raises(WorktreeError, match="contains path separators"):
            worktree_manager.create_worktree(branch_name, agent_name)

    @patch.object(WorktreeManager, "_validate_worktree_path")
    @patch.object(WorktreeManager, "_run_git_command")
    def test_create_worktree_unsafe_path(self, mock_run_git, mock_validate, worktree_manager):
        """Test worktree creation with unsafe path."""
        mock_validate.return_value = False
        mock_run_git.return_value = ""

        with pytest.raises(WorktreeError, match="outside allowed boundaries"):
            worktree_manager.create_worktree("branch", "agent")

    def test_remove_worktree_cocode_directory(self, worktree_manager):
        """Test removing a cocode directory that's not a worktree."""
        # Create a regular directory with cocode prefix
        cocode_dir = worktree_manager.repo_path.parent / "cocode_test"
        cocode_dir.mkdir()
        (cocode_dir / "file.txt").write_text("test")

        # Mock _list_all_worktrees to return empty
        with patch.object(worktree_manager, "_list_all_worktrees", return_value={}):
            # Should remove it
            worktree_manager.remove_worktree(cocode_dir)
            assert not cocode_dir.exists()

    @patch("cocode.git.worktree.subprocess.run")
    def test_list_all_worktrees_parsing(self, mock_run, worktree_manager):
        """Test parsing of git worktree list output."""
        mock_run.return_value = Mock(
            stdout=(
                "worktree /path/to/repo\n"
                "HEAD abcdef123\n"
                "branch refs/heads/main\n"
                "\n"
                "worktree /path/to/cocode_agent1\n"
                "HEAD fedcba321\n"
                "branch refs/heads/test-branch\n"
                "\n"
                "worktree /path/to/bare\n"
                "bare\n"
            ),
            stderr="",
            returncode=0,
        )

        worktrees = worktree_manager._list_all_worktrees()

        assert len(worktrees) == 2
        assert worktrees["/path/to/repo"] == "refs/heads/main"
        assert worktrees["/path/to/cocode_agent1"] == "refs/heads/test-branch"
        assert "/path/to/bare" not in worktrees

    @patch.object(WorktreeManager, "_list_all_worktrees")
    def test_list_worktrees_filters_cocode_only(self, mock_list_all, worktree_manager):
        """Test that list_worktrees only returns cocode worktrees."""
        mock_list_all.return_value = {
            "/path/to/repo": "refs/heads/main",
            "/path/to/cocode_agent1": "refs/heads/branch1",
            "/path/to/other_worktree": "refs/heads/branch2",
            "/path/to/cocode_agent2": "refs/heads/branch3",
        }

        worktrees = worktree_manager.list_worktrees()

        assert len(worktrees) == 2
        assert Path("/path/to/cocode_agent1") in worktrees
        assert Path("/path/to/cocode_agent2") in worktrees
        assert Path("/path/to/other_worktree") not in worktrees

    def test_constant_prefix(self):
        """Test that COCODE_PREFIX constant is defined correctly."""
        assert WorktreeManager.COCODE_PREFIX == "cocode_"

    @patch.object(WorktreeManager, "_list_all_worktrees")
    def test_get_worktree_info_not_worktree(self, mock_list_all, worktree_manager):
        """Test getting info for non-worktree path."""
        mock_list_all.return_value = {}
        non_worktree = worktree_manager.repo_path.parent / "not_a_worktree"

        with pytest.raises(WorktreeError, match="Not a git worktree"):
            worktree_manager.get_worktree_info(non_worktree)

    @patch.object(WorktreeManager, "_list_all_worktrees")
    @patch.object(WorktreeManager, "_run_git_command")
    def test_get_worktree_info_success(self, mock_run_git, mock_list_all, worktree_manager):
        """Test getting worktree information."""
        worktree_path = Path("/path/to/cocode_test")
        mock_list_all.return_value = {str(worktree_path): "refs/heads/test-branch"}

        def side_effect(args, cwd=None):
            if args[0] == "log":
                return "abc123 Test commit"
            elif args[0] == "status":
                return ""
            return ""

        mock_run_git.side_effect = side_effect

        info = worktree_manager.get_worktree_info(worktree_path)

        assert info["path"] == worktree_path
        assert info["branch"] == "refs/heads/test-branch"
        assert info["last_commit"] == "abc123 Test commit"
        assert info["has_changes"] is False

    @patch.object(WorktreeManager, "list_worktrees")
    @patch.object(WorktreeManager, "remove_worktree")
    def test_cleanup_worktrees(self, mock_remove, mock_list, worktree_manager):
        """Test cleaning up all cocode worktrees."""
        worktrees = [
            Path("/path/to/cocode_agent1"),
            Path("/path/to/cocode_agent2"),
            Path("/path/to/cocode_agent3"),
        ]
        mock_list.return_value = worktrees
        mock_remove.return_value = None

        count = worktree_manager.cleanup_worktrees()

        assert count == 3
        assert mock_remove.call_count == 3

    @patch.object(WorktreeManager, "list_worktrees")
    @patch.object(WorktreeManager, "remove_worktree")
    @patch.object(WorktreeManager, "_run_git_command")
    def test_cleanup_worktrees_with_error(
        self, mock_run_git, mock_remove, mock_list, worktree_manager
    ):
        """Test cleanup when some worktrees fail to remove."""
        worktrees = [
            Path("/path/to/cocode_agent1"),
            Path("/path/to/cocode_agent2"),
        ]
        mock_list.return_value = worktrees
        mock_remove.side_effect = [
            WorktreeError("Cannot remove"),
            None,
        ]
        mock_run_git.return_value = ""  # For prune

        count = worktree_manager.cleanup_worktrees()

        assert count == 1  # Only one was successfully removed
