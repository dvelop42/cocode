"""Unit tests for worktree sync functionality."""

from unittest.mock import Mock, patch

import pytest

from cocode.git.sync import ConflictType, SyncStatus, WorktreeSync


@pytest.fixture
def mock_repo_path(tmp_path):
    """Create a mock repository path."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()
    return repo_path


@pytest.fixture
def sync_manager(mock_repo_path):
    """Create a WorktreeSync instance."""
    return WorktreeSync(mock_repo_path)


class TestWorktreeSync:
    """Test WorktreeSync class."""

    def test_init(self, mock_repo_path):
        """Test WorktreeSync initialization."""
        sync = WorktreeSync(mock_repo_path)
        assert sync.repo_path == mock_repo_path.resolve()

    @patch("subprocess.run")
    def test_has_uncommitted_changes_clean(self, mock_run, sync_manager, tmp_path):
        """Test detecting clean working tree."""
        mock_run.return_value = Mock(stdout="", returncode=0)

        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        result = sync_manager._has_uncommitted_changes(worktree_path)
        assert result is False

        mock_run.assert_called_once_with(
            ["git", "status", "--porcelain"], cwd=worktree_path, capture_output=True, text=True
        )

    @patch("subprocess.run")
    def test_has_uncommitted_changes_dirty(self, mock_run, sync_manager, tmp_path):
        """Test detecting uncommitted changes."""
        mock_run.return_value = Mock(stdout="M  file.txt\n", returncode=0)

        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        result = sync_manager._has_uncommitted_changes(worktree_path)
        assert result is True

    @patch("subprocess.run")
    def test_stash_changes_success(self, mock_run, sync_manager, tmp_path):
        """Test successful stashing."""
        mock_run.side_effect = [
            Mock(stdout="", returncode=0),  # stash push
            Mock(stdout="abc123\n", returncode=0),  # rev-parse
        ]

        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        result = sync_manager._stash_changes(worktree_path)
        assert result == "abc123"

    @patch("subprocess.run")
    def test_stash_changes_failure(self, mock_run, sync_manager, tmp_path):
        """Test failed stashing."""
        mock_run.return_value = Mock(stdout="", returncode=1)

        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        result = sync_manager._stash_changes(worktree_path)
        assert result is None

    @patch("subprocess.run")
    def test_fetch_updates_success(self, mock_run, sync_manager, tmp_path):
        """Test successful fetch."""
        mock_run.return_value = Mock(stdout="", returncode=0)

        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        result = sync_manager._fetch_updates(worktree_path, "origin")
        assert result is True

        mock_run.assert_called_once_with(
            ["git", "fetch", "origin", "--prune"], cwd=worktree_path, capture_output=True, text=True
        )

    @patch("subprocess.run")
    def test_check_divergence_up_to_date(self, mock_run, sync_manager, tmp_path):
        """Test checking divergence - up to date."""
        mock_run.side_effect = [
            Mock(stdout="main\n", returncode=0),  # current branch
            Mock(stdout="0\t0\n", returncode=0),  # rev-list
        ]

        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        result = sync_manager._check_divergence(worktree_path, "origin", "main")
        assert result == "up-to-date"

    @patch("subprocess.run")
    def test_check_divergence_behind(self, mock_run, sync_manager, tmp_path):
        """Test checking divergence - behind."""
        mock_run.side_effect = [
            Mock(stdout="main\n", returncode=0),  # current branch
            Mock(stdout="3\t0\n", returncode=0),  # rev-list
        ]

        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        result = sync_manager._check_divergence(worktree_path, "origin", "main")
        assert result == "behind"

    @patch("subprocess.run")
    def test_check_divergence_ahead(self, mock_run, sync_manager, tmp_path):
        """Test checking divergence - ahead."""
        mock_run.side_effect = [
            Mock(stdout="main\n", returncode=0),  # current branch
            Mock(stdout="0\t2\n", returncode=0),  # rev-list
        ]

        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        result = sync_manager._check_divergence(worktree_path, "origin", "main")
        assert result == "ahead"

    @patch("subprocess.run")
    def test_check_divergence_diverged(self, mock_run, sync_manager, tmp_path):
        """Test checking divergence - diverged."""
        mock_run.side_effect = [
            Mock(stdout="main\n", returncode=0),  # current branch
            Mock(stdout="3\t2\n", returncode=0),  # rev-list
        ]

        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        result = sync_manager._check_divergence(worktree_path, "origin", "main")
        assert result == "diverged"

    @patch("subprocess.run")
    def test_rebase_success(self, mock_run, sync_manager, tmp_path):
        """Test successful rebase."""
        mock_run.return_value = Mock(stdout="", returncode=0)

        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        result = sync_manager._rebase(worktree_path, "origin/main")
        assert result == {"success": True}

    @patch("subprocess.run")
    def test_rebase_conflict(self, mock_run, sync_manager, tmp_path):
        """Test rebase with conflicts."""
        mock_run.side_effect = [
            Mock(stdout="", returncode=1),  # rebase
            Mock(stdout="UU file.txt\n", returncode=0),  # status
        ]

        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        result = sync_manager._rebase(worktree_path, "origin/main")
        assert result == {"success": False, "conflict": True}

    @patch("subprocess.run")
    def test_get_conflicted_files(self, mock_run, sync_manager, tmp_path):
        """Test getting list of conflicted files."""
        mock_run.return_value = Mock(stdout="file1.txt\nfile2.py\n", returncode=0)

        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        result = sync_manager._get_conflicted_files(worktree_path)
        assert result == ["file1.txt", "file2.py"]

    @patch("subprocess.run")
    def test_detect_conflicts(self, mock_run, sync_manager, tmp_path):
        """Test detecting conflicts."""
        mock_run.return_value = Mock(stdout="conflict.txt\n", returncode=0)

        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        has_conflicts, files = sync_manager.detect_conflicts(worktree_path)
        assert has_conflicts is True
        assert files == ["conflict.txt"]

    @patch.object(WorktreeSync, "_has_uncommitted_changes")
    @patch.object(WorktreeSync, "_fetch_updates")
    @patch.object(WorktreeSync, "_check_divergence")
    def test_sync_clean(self, mock_divergence, mock_fetch, mock_changes, sync_manager, tmp_path):
        """Test sync when already up to date."""
        mock_changes.return_value = False
        mock_fetch.return_value = True
        mock_divergence.return_value = "up-to-date"

        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        result = sync_manager.sync(worktree_path)

        assert result.status == SyncStatus.CLEAN
        assert result.worktree_path == worktree_path.resolve()
        assert result.message == "Sync completed successfully"

    @patch.object(WorktreeSync, "_has_uncommitted_changes")
    @patch.object(WorktreeSync, "_fetch_updates")
    @patch.object(WorktreeSync, "_check_divergence")
    @patch.object(WorktreeSync, "_fast_forward")
    def test_sync_fast_forward(
        self, mock_ff, mock_divergence, mock_fetch, mock_changes, sync_manager, tmp_path
    ):
        """Test sync with fast-forward."""
        mock_changes.return_value = False
        mock_fetch.return_value = True
        mock_divergence.return_value = "behind"
        mock_ff.return_value = True

        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        result = sync_manager.sync(worktree_path)

        assert result.status == SyncStatus.UPDATED
        assert result.worktree_path == worktree_path.resolve()
        mock_ff.assert_called_once()

    @patch.object(WorktreeSync, "_has_uncommitted_changes")
    @patch.object(WorktreeSync, "_stash_changes")
    @patch.object(WorktreeSync, "_fetch_updates")
    @patch.object(WorktreeSync, "_check_divergence")
    @patch.object(WorktreeSync, "_rebase")
    @patch.object(WorktreeSync, "_apply_stash")
    def test_sync_with_stash(
        self,
        mock_apply,
        mock_rebase,
        mock_divergence,
        mock_fetch,
        mock_stash,
        mock_changes,
        sync_manager,
        tmp_path,
    ):
        """Test sync with stashing."""
        mock_changes.side_effect = [True, True]  # Has changes before and after
        mock_stash.return_value = "stash@{0}"
        mock_fetch.return_value = True
        mock_divergence.return_value = "diverged"
        mock_rebase.return_value = {"success": True}
        mock_apply.return_value = True

        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        result = sync_manager.sync(worktree_path)

        assert result.status == SyncStatus.STASHED
        assert result.stash_ref == "stash@{0}"
        assert result.worktree_path == worktree_path.resolve()

    @patch.object(WorktreeSync, "_has_uncommitted_changes")
    @patch.object(WorktreeSync, "_fetch_updates")
    @patch.object(WorktreeSync, "_check_divergence")
    @patch.object(WorktreeSync, "_rebase")
    @patch.object(WorktreeSync, "_get_conflicted_files")
    def test_sync_with_conflicts(
        self,
        mock_conflicts,
        mock_rebase,
        mock_divergence,
        mock_fetch,
        mock_changes,
        sync_manager,
        tmp_path,
    ):
        """Test sync with conflicts."""
        mock_changes.return_value = False
        mock_fetch.return_value = True
        mock_divergence.return_value = "diverged"
        mock_rebase.return_value = {"success": False, "conflict": True}
        mock_conflicts.return_value = ["file1.txt", "file2.py"]

        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        result = sync_manager.sync(worktree_path)

        assert result.status == SyncStatus.CONFLICTS
        assert result.conflict_type == ConflictType.REBASE_CONFLICT
        assert result.conflicts == ["file1.txt", "file2.py"]
        assert result.worktree_path == worktree_path.resolve()

    @patch.object(WorktreeSync, "_has_uncommitted_changes")
    @patch.object(WorktreeSync, "_fetch_updates")
    def test_sync_fetch_failure(self, mock_fetch, mock_changes, sync_manager, tmp_path):
        """Test sync when fetch fails."""
        mock_changes.return_value = False
        mock_fetch.return_value = False

        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        result = sync_manager.sync(worktree_path)

        assert result.status == SyncStatus.ERROR
        assert "Failed to fetch" in result.message

    @patch("subprocess.run")
    def test_abort_rebase(self, mock_run, sync_manager, tmp_path):
        """Test aborting a rebase."""
        mock_run.return_value = Mock(stdout="", returncode=0)

        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        result = sync_manager.abort_rebase(worktree_path)
        assert result is True

        mock_run.assert_called_once_with(
            ["git", "rebase", "--abort"], cwd=worktree_path, capture_output=True, text=True
        )

    @patch("subprocess.run")
    def test_abort_merge(self, mock_run, sync_manager, tmp_path):
        """Test aborting a merge."""
        mock_run.return_value = Mock(stdout="", returncode=0)

        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        result = sync_manager.abort_merge(worktree_path)
        assert result is True

        mock_run.assert_called_once_with(
            ["git", "merge", "--abort"], cwd=worktree_path, capture_output=True, text=True
        )
