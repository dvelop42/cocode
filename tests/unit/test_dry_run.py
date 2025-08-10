"""Test dry run functionality across the application."""

from unittest.mock import Mock, patch

import pytest

from cocode.git.worktree import WorktreeManager
from cocode.github.issues import IssueManager
from cocode.tui.app import CocodeApp
from cocode.utils.dry_run import DryRunFormatter, get_dry_run_context


class TestDryRunCLI:
    """Test dry run functionality in CLI commands."""

    @pytest.mark.skip("CLI testing needs to be updated to work with full app context")
    def test_cli_integration_placeholder(self):
        """Placeholder for CLI integration tests."""
        # These tests need to be rewritten to test through the main CLI app
        # rather than individual command functions
        pass


class TestWorktreeManagerDryRun:
    """Test WorktreeManager dry run functionality."""

    def test_worktree_manager_dry_run_init(self, tmp_path):
        """Test WorktreeManager initialization with dry run."""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        manager = WorktreeManager(repo_path, dry_run=True)

        assert manager.dry_run is True
        assert manager.repo_path == repo_path

    def test_create_worktree_dry_run(self, tmp_path, caplog):
        """Test worktree creation in dry run mode."""
        import logging
        # Set logging level to capture info messages
        caplog.set_level(logging.INFO)
        
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        manager = WorktreeManager(repo_path, dry_run=True)

        with patch.object(manager, "_run_git_command") as mock_git:
            mock_git.return_value = "main"  # Mock default branch

            result_path = manager.create_worktree("test-branch", "test-agent")

            # Should return the expected path
            expected_path = repo_path.parent / "cocode_test-agent"
            assert result_path == expected_path

            # Should log dry run operation
            assert "[DRY RUN]" in caplog.text
            assert "Would create worktree" in caplog.text

    def test_remove_worktree_dry_run(self, tmp_path, caplog):
        """Test worktree removal in dry run mode."""
        import logging
        caplog.set_level(logging.INFO)
        
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        worktree_path = repo_path.parent / "cocode_test"
        worktree_path.mkdir()

        manager = WorktreeManager(repo_path, dry_run=True)

        with patch.object(manager, "_list_all_worktrees") as mock_list:
            mock_list.return_value = {str(worktree_path): "test-branch"}

            manager.remove_worktree(worktree_path)

            # Directory should still exist in dry run mode
            assert worktree_path.exists()

            # Should log dry run operation
            assert "[DRY RUN]" in caplog.text
            assert "Would remove worktree" in caplog.text

    def test_git_command_dry_run(self, tmp_path, caplog):
        """Test git command execution in dry run mode."""
        import logging
        caplog.set_level(logging.INFO)
        
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        manager = WorktreeManager(repo_path, dry_run=True)

        # Test write command (should be skipped)
        result = manager._run_git_command(["worktree", "add", "test"])
        assert result == "[DRY RUN]"
        assert "[DRY RUN] Would execute" in caplog.text

        # Test read command (should execute normally)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = "test output"
            mock_run.return_value.returncode = 0

            result = manager._run_git_command(["status", "--porcelain"])
            assert result == "test output"
            mock_run.assert_called_once()


class TestGitHubIssuesDryRun:
    """Test GitHub issues dry run functionality."""

    def test_issue_manager_dry_run_init(self):
        """Test IssueManager initialization with dry run."""
        manager = IssueManager(dry_run=True)

        assert manager.dry_run is True

        # Should not verify gh CLI in dry run mode
        with patch.object(manager, "_verify_gh_cli") as mock_verify:
            IssueManager(dry_run=True)
            mock_verify.assert_not_called()

    def test_fetch_issues_dry_run(self, caplog):
        """Test fetching issues in dry run mode."""
        import logging
        caplog.set_level(logging.INFO)
        
        manager = IssueManager(dry_run=True)

        issues = manager.fetch_issues(state="open", limit=10)

        assert len(issues) == 1
        assert issues[0]["title"] == "[DRY RUN] Sample Issue"
        assert issues[0]["labels"] == ["dry-run"]
        assert "[DRY RUN] Would execute" in caplog.text

    def test_get_issue_dry_run(self, caplog):
        """Test getting a specific issue in dry run mode."""
        import logging
        caplog.set_level(logging.INFO)
        
        manager = IssueManager(dry_run=True)

        issue = manager.get_issue(123)

        assert issue["number"] == 123
        assert issue["title"] == "[DRY RUN] Sample Issue #123"
        assert issue["labels"] == ["dry-run"]
        assert "[DRY RUN] Would execute" in caplog.text

    def test_get_issue_body_dry_run(self):
        """Test getting issue body in dry run mode."""
        manager = IssueManager(dry_run=True)

        body = manager.get_issue_body(456)

        assert body == "This is a sample issue #456 in dry run mode"


class TestDryRunFormatter:
    """Test dry run formatting utilities."""

    def test_formatter_disabled(self, capsys):
        """Test formatter when dry run is disabled."""
        formatter = DryRunFormatter(enabled=False)

        formatter.format_operation("test operation")
        formatter.format_command(["git", "add", "."])
        formatter.format_file_operation("create", "test.txt", "content")

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_formatter_enabled(self, capsys):
        """Test formatter when dry run is enabled."""
        formatter = DryRunFormatter(enabled=True)

        formatter.format_operation("test operation", "with details")

        captured = capsys.readouterr()
        assert "Would test operation" in captured.out
        assert "with details" in captured.out

    def test_format_command(self, capsys):
        """Test command formatting."""
        formatter = DryRunFormatter(enabled=True)

        formatter.format_command(["git", "commit", "-m", "test"])

        captured = capsys.readouterr()
        assert "Would execute:" in captured.out
        assert "git commit -m test" in captured.out

    def test_format_file_operation(self, capsys):
        """Test file operation formatting."""
        formatter = DryRunFormatter(enabled=True)

        content = "line1\nline2\nline3\nline4\nline5\nline6\nline7"
        formatter.format_file_operation("create", "test.txt", content)

        captured = capsys.readouterr()
        assert "Would create file:" in captured.out
        assert "test.txt" in captured.out
        assert "line1" in captured.out
        assert "..." in captured.out  # Should truncate long content

    def test_show_summary(self, capsys):
        """Test summary display."""
        formatter = DryRunFormatter(enabled=True)

        operations = ["Create worktree", "Run agent", "Create PR"]
        formatter.show_summary(operations)

        captured = capsys.readouterr()
        assert "DRY RUN SUMMARY" in captured.out
        assert "Create worktree" in captured.out
        assert "Run agent" in captured.out
        assert "Create PR" in captured.out

    def test_get_dry_run_context(self):
        """Test extracting dry run context."""
        # Mock context with dry_run flag
        mock_ctx = Mock()
        mock_ctx.obj = {"dry_run": True}

        result = get_dry_run_context(mock_ctx)
        assert result is True

        # Mock context without dry_run flag
        mock_ctx.obj = {}
        result = get_dry_run_context(mock_ctx)
        assert result is False

        # Mock context without obj
        mock_ctx.obj = None
        result = get_dry_run_context(mock_ctx)
        assert result is False


class TestTUIDryRun:
    """Test TUI dry run indicators."""

    def test_tui_dry_run_mode(self):
        """Test TUI with dry run mode enabled."""
        app = CocodeApp(dry_run=True)

        assert app.dry_run is True

        # Test title setting
        app.on_mount()
        assert app.title == "Cocode - DRY RUN MODE"

    def test_tui_normal_mode(self):
        """Test TUI in normal mode."""
        app = CocodeApp(dry_run=False)

        assert app.dry_run is False

        # Test title setting
        app.on_mount()
        assert app.title == "Cocode"

    @pytest.mark.skip("TUI compose tests need active Textual app context")
    def test_tui_compose_placeholder(self):
        """Placeholder for TUI composition tests."""
        # These tests need to be rewritten to work with Textual's testing framework
        pass


class TestDryRunIntegration:
    """Test dry run functionality in integration scenarios."""

    def test_end_to_end_dry_run_workflow(self, tmp_path, caplog):
        """Test a complete dry run workflow."""
        import logging
        caplog.set_level(logging.INFO)
        
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        # Initialize components in dry run mode
        worktree_manager = WorktreeManager(repo_path, dry_run=True)
        issue_manager = IssueManager(dry_run=True)

        # Mock the git commands to avoid actual git calls
        with patch.object(worktree_manager, "_run_git_command") as mock_git:
            mock_git.return_value = "main"

            # Simulate workflow
            issue = issue_manager.get_issue(123)
            assert issue["title"] == "[DRY RUN] Sample Issue #123"

            worktree_path = worktree_manager.create_worktree("test-branch", "test-agent")
            expected_path = repo_path.parent / "cocode_test-agent"
            assert worktree_path == expected_path

            # Should not create actual worktree
            assert not worktree_path.exists()

            # Should have dry run logs
            assert "[DRY RUN]" in caplog.text
            assert "Would create worktree" in caplog.text
            assert "Would execute: gh issue view" in caplog.text
