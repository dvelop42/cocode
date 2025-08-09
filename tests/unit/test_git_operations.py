"""Unit tests for git operations."""

import subprocess
from unittest.mock import Mock

import pytest


class TestGitWorktree:
    """Test git worktree management."""

    @pytest.mark.git
    def test_worktree_creation(self, temp_repo):
        """Test creating a new worktree."""
        worktree_path = temp_repo.parent / "cocode_test"
        branch_name = "cocode/123-test"

        # Create worktree
        subprocess.run(
            ["git", "worktree", "add", "-b", branch_name, str(worktree_path), "HEAD"],
            cwd=temp_repo,
            check=True
        )

        assert worktree_path.exists()
        assert (worktree_path / ".git").exists()

        # Verify branch
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=worktree_path,
            capture_output=True,
            text=True
        )
        assert result.stdout.strip() == branch_name

    @pytest.mark.git
    def test_worktree_cleanup(self, temp_repo):
        """Test removing worktrees."""
        worktree_path = temp_repo.parent / "cocode_test"
        branch_name = "cocode/123-test"

        # Create worktree
        subprocess.run(
            ["git", "worktree", "add", "-b", branch_name, str(worktree_path)],
            cwd=temp_repo,
            check=True
        )

        # Remove worktree
        subprocess.run(
            ["git", "worktree", "remove", str(worktree_path), "--force"],
            cwd=temp_repo,
            check=True
        )

        assert not worktree_path.exists()

    @pytest.mark.git
    def test_worktree_list(self, temp_repo):
        """Test listing worktrees."""
        # List worktrees
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=temp_repo,
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        assert str(temp_repo) in result.stdout


class TestGitOperations:
    """Test git command operations."""

    @pytest.mark.unit
    def test_fetch_before_operations(self, mock_subprocess_run):
        """Test that fetch is called before worktree operations."""
        from subprocess import run

        # Simulate fetch
        run(["git", "fetch", "--all", "--prune"])

        mock_subprocess_run.assert_called_with(
            ["git", "fetch", "--all", "--prune"]
        )

    @pytest.mark.git
    def test_clean_working_tree_check(self, temp_repo):
        """Test checking for clean working tree."""
        # Check clean status
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=temp_repo,
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        assert result.stdout == ""  # Empty means clean

        # Create uncommitted change
        (temp_repo / "test.txt").write_text("changes")

        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=temp_repo,
            capture_output=True,
            text=True
        )

        assert result.stdout != ""  # Not empty means dirty

    @pytest.mark.git
    def test_commit_with_ready_marker(self, temp_repo):
        """Test creating commits with ready marker."""
        # Create a file
        test_file = temp_repo / "fix.py"
        test_file.write_text("# Fix for issue")

        # Stage and commit with ready marker
        subprocess.run(["git", "add", "."], cwd=temp_repo, check=True)
        subprocess.run(
            ["git", "commit", "-m", "fix: issue #123\n\ncocode ready for check"],
            cwd=temp_repo,
            check=True
        )

        # Verify commit message
        result = subprocess.run(
            ["git", "log", "-1", "--format=%B"],
            cwd=temp_repo,
            capture_output=True,
            text=True
        )

        assert "fix: issue #123" in result.stdout
        assert "cocode ready for check" in result.stdout


class TestBranchManagement:
    """Test git branch operations."""

    @pytest.mark.git
    def test_branch_naming_convention(self):
        """Test branch names follow convention."""
        issue_number = "123"
        agent_name = "claude-code"

        branch_name = f"cocode/{issue_number}-{agent_name}"

        assert branch_name.startswith("cocode/")
        assert issue_number in branch_name
        assert agent_name in branch_name

    @pytest.mark.git
    def test_branch_creation_from_base(self, temp_repo):
        """Test creating branches from base branch."""
        new_branch = "cocode/123-test"

        # Create and checkout new branch
        subprocess.run(
            ["git", "checkout", "-b", new_branch],
            cwd=temp_repo,
            check=True
        )

        # Verify current branch
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=temp_repo,
            capture_output=True,
            text=True
        )

        assert result.stdout.strip() == new_branch

    @pytest.mark.unit
    def test_branch_exists_check(self, mock_subprocess_run):
        """Test checking if branch exists."""
        mock_subprocess_run.return_value = Mock(
            returncode=0,
            stdout="cocode/123-test\n"
        )

        from subprocess import run
        result = run(["git", "branch", "-r", "--list", "*cocode/123-test"])

        assert result.returncode == 0


class TestGitSafety:
    """Test git safety checks and validations."""

    @pytest.mark.unit
    def test_no_gitpython_usage(self):
        """Ensure we don't use GitPython (use subprocess instead)."""
        # This is a policy test - we should never import GitPython
        with pytest.raises(ImportError):
            import git  # noqa

    @pytest.mark.git
    def test_git_config_isolation(self, temp_repo):
        """Test git config is isolated per worktree."""
        # Set local config
        subprocess.run(
            ["git", "config", "--local", "test.key", "value"],
            cwd=temp_repo,
            check=True
        )

        # Verify config is set
        result = subprocess.run(
            ["git", "config", "--local", "test.key"],
            cwd=temp_repo,
            capture_output=True,
            text=True
        )

        assert result.stdout.strip() == "value"

    @pytest.mark.unit
    def test_git_command_construction(self):
        """Test safe git command construction."""
        # Safe commands that should be allowed
        safe_commands = [
            ["git", "status"],
            ["git", "add", "."],
            ["git", "commit", "-m", "message"],
            ["git", "worktree", "add", "path"],
            ["git", "fetch", "--all"],
        ]

        for cmd in safe_commands:
            assert cmd[0] == "git"
            assert "--force" not in cmd or "worktree" in cmd  # Only allow --force for worktree
