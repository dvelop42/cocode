"""Test dry run functionality across the application."""

from unittest.mock import Mock, patch

from typer.testing import CliRunner

from cocode.cli.clean import clean_command
from cocode.cli.init import init_command
from cocode.cli.run import run_command
from cocode.git.worktree import WorktreeManager
from cocode.github.issues import IssueManager
from cocode.tui.app import CocodeApp
from cocode.utils.dry_run import DryRunFormatter, get_dry_run_context


class TestDryRunCLI:
    """Test dry run functionality in CLI commands."""

    def test_init_dry_run(self):
        """Test init command in dry run mode."""
        runner = CliRunner()

        with patch("cocode.cli.init.discover_agents") as mock_discover:
            mock_discover.return_value = [
                Mock(
                    name="claude-code",
                    installed=True,
                    path="/usr/bin/claude-code",
                    aliases=["claude-code"],
                )
            ]

            with patch("cocode.cli.init.ConfigManager") as mock_config:
                mock_config_instance = Mock()
                mock_config.return_value = mock_config_instance

                # Test with dry run
                result = runner.invoke(init_command, ["--no-interactive", "--dry-run"])

                assert result.exit_code == 0
                assert "DRY RUN MODE" in result.output
                assert "Would save configuration" in result.output
                # Config should not be saved in dry run mode
                mock_config_instance.save.assert_not_called()

    def test_run_dry_run(self):
        """Test run command in dry run mode."""
        runner = CliRunner()

        # Mock context to include dry_run flag
        mock_ctx = Mock()
        mock_ctx.obj = {"dry_run": True}

        with patch("cocode.cli.run.typer.Context") as mock_context:
            mock_context.get_current.return_value = mock_ctx

            result = runner.invoke(run_command, ["123", "--dry-run"])

            assert result.exit_code == 1  # Command not implemented yet
            assert "DRY RUN MODE" in result.output
            assert "Would run agents on issue #123" in result.output

    def test_clean_dry_run(self, tmp_path):
        """Test clean command in dry run mode."""
        runner = CliRunner()

        # Create a mock git repository
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        with patch("cocode.cli.clean.Path.cwd", return_value=repo_path):
            with patch("cocode.git.worktree.WorktreeManager") as mock_manager:
                mock_instance = Mock()
                mock_manager.return_value = mock_instance
                mock_instance.list_worktrees.return_value = [repo_path / "cocode_test"]
                mock_instance.get_worktree_info.return_value = {
                    "path": repo_path / "cocode_test",
                    "branch": "test-branch",
                    "last_commit": "abc123 Test commit",
                    "has_changes": False,
                }

                # Mock context to include dry_run flag
                mock_ctx = Mock()
                mock_ctx.obj = {"dry_run": True}

                with patch("cocode.cli.clean.typer.Context") as mock_context:
                    mock_context.get_current.return_value = mock_ctx

                    result = runner.invoke(clean_command, ["--all", "--force", "--dry-run"])

                    assert "DRY RUN MODE" in result.output
                    assert "Would remove" in result.output
                    # Remove should not be called in dry run mode
                    mock_instance.remove_worktree.assert_not_called()


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
        manager = IssueManager(dry_run=True)

        issues = manager.fetch_issues(state="open", limit=10)

        assert len(issues) == 1
        assert issues[0]["title"] == "[DRY RUN] Sample Issue"
        assert issues[0]["labels"] == ["dry-run"]
        assert "[DRY RUN] Would execute" in caplog.text

    def test_get_issue_dry_run(self, caplog):
        """Test getting a specific issue in dry run mode."""
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

    def test_tui_compose_dry_run(self):
        """Test TUI composition with dry run indicator."""
        app = CocodeApp(dry_run=True)

        # Get composed widgets
        widgets = list(app.compose())

        # Should have dry run indicator
        dry_run_widgets = [w for w in widgets if hasattr(w, "id") and w.id == "dry-run-indicator"]
        assert len(dry_run_widgets) == 1

        indicator = dry_run_widgets[0]
        assert "DRY RUN MODE" in str(indicator.renderable)

    def test_tui_compose_normal(self):
        """Test TUI composition without dry run indicator."""
        app = CocodeApp(dry_run=False)

        # Get composed widgets
        widgets = list(app.compose())

        # Should not have dry run indicator
        dry_run_widgets = [w for w in widgets if hasattr(w, "id") and w.id == "dry-run-indicator"]
        assert len(dry_run_widgets) == 0


class TestDryRunIntegration:
    """Test dry run functionality in integration scenarios."""

    def test_end_to_end_dry_run_workflow(self, tmp_path, caplog):
        """Test a complete dry run workflow."""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        # Initialize components in dry run mode
        worktree_manager = WorktreeManager(repo_path, dry_run=True)
        issue_manager = IssueManager(dry_run=True)

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
