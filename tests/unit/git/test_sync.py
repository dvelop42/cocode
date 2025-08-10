"""Tests for worktree synchronization."""

from pathlib import Path
from unittest.mock import Mock, patch

from cocode.git.sync import (
    ConflictType,
    SyncResult,
    SyncStatus,
    WorktreeSync,
)


class TestSyncEnums:
    """Tests for sync-related enums."""

    def test_sync_status_values(self):
        """Test SyncStatus enum values."""
        assert SyncStatus.CLEAN.value == "clean"
        assert SyncStatus.UPDATED.value == "updated"
        assert SyncStatus.CONFLICTS.value == "conflicts"
        assert SyncStatus.STASHED.value == "stashed"
        assert SyncStatus.ERROR.value == "error"

    def test_conflict_type_values(self):
        """Test ConflictType enum values."""
        assert ConflictType.MERGE_CONFLICT.value == "merge_conflict"
        assert ConflictType.REBASE_CONFLICT.value == "rebase_conflict"
        assert ConflictType.UNCOMMITTED_CHANGES.value == "uncommitted_changes"
        assert ConflictType.DIVERGED.value == "diverged"


class TestSyncResult:
    """Tests for SyncResult dataclass."""

    def test_sync_result_creation(self):
        """Test creating a SyncResult instance."""
        path = Path("/test/path")
        result = SyncResult(status=SyncStatus.CLEAN, worktree_path=path, message="Test message")

        assert result.status == SyncStatus.CLEAN
        assert result.worktree_path == path
        assert result.conflicts is None
        assert result.conflict_type is None
        assert result.stash_ref is None
        assert result.message == "Test message"

    def test_sync_result_with_conflicts(self):
        """Test SyncResult with conflicts."""
        path = Path("/test/path")
        conflicts = ["file1.py", "file2.py"]

        result = SyncResult(
            status=SyncStatus.CONFLICTS,
            worktree_path=path,
            conflicts=conflicts,
            conflict_type=ConflictType.MERGE_CONFLICT,
            stash_ref="stash@{0}",
            message="Conflicts detected",
        )

        assert result.status == SyncStatus.CONFLICTS
        assert result.conflicts == conflicts
        assert result.conflict_type == ConflictType.MERGE_CONFLICT
        assert result.stash_ref == "stash@{0}"


class TestWorktreeSync:
    """Tests for WorktreeSync class."""

    def test_init(self, temp_repo):
        """Test WorktreeSync initialization."""
        sync = WorktreeSync(temp_repo)
        assert sync.repo_path == temp_repo.resolve()

    def test_stash_message_constant(self):
        """Test that STASH_MESSAGE constant is defined."""
        assert WorktreeSync.STASH_MESSAGE == "cocode: auto-stash before sync"

    @patch("subprocess.run")
    def test_has_uncommitted_changes_true(self, mock_run, temp_repo):
        """Test _has_uncommitted_changes when changes exist."""
        sync = WorktreeSync(temp_repo)

        # Mock git status output with changes
        mock_run.return_value = Mock(stdout="M  file.py\n", returncode=0)

        result = sync._has_uncommitted_changes(temp_repo)
        assert result is True

        mock_run.assert_called_once_with(
            ["git", "status", "--porcelain"], cwd=temp_repo, capture_output=True, text=True
        )

    @patch("subprocess.run")
    def test_has_uncommitted_changes_false(self, mock_run, temp_repo):
        """Test _has_uncommitted_changes when no changes exist."""
        sync = WorktreeSync(temp_repo)

        # Mock git status output with no changes
        mock_run.return_value = Mock(stdout="", returncode=0)

        result = sync._has_uncommitted_changes(temp_repo)
        assert result is False

    @patch("subprocess.run")
    def test_stash_changes_success(self, mock_run, temp_repo):
        """Test _stash_changes when stashing succeeds."""
        sync = WorktreeSync(temp_repo)

        # Mock successful stash and rev-parse
        mock_run.side_effect = [
            Mock(returncode=0),  # git stash push
            Mock(returncode=0, stdout="abc123\n"),  # git rev-parse
        ]

        result = sync._stash_changes(temp_repo)
        assert result == "abc123"

        assert mock_run.call_count == 2
        # Check stash command
        stash_call = mock_run.call_args_list[0]
        assert stash_call[0][0] == ["git", "stash", "push", "-m", sync.STASH_MESSAGE]

    @patch("subprocess.run")
    def test_stash_changes_failure(self, mock_run, temp_repo):
        """Test _stash_changes when stashing fails."""
        sync = WorktreeSync(temp_repo)

        # Mock failed stash
        mock_run.return_value = Mock(returncode=1)

        result = sync._stash_changes(temp_repo)
        assert result is None

    @patch("subprocess.run")
    def test_apply_stash_success(self, mock_run, temp_repo):
        """Test _apply_stash when application succeeds."""
        sync = WorktreeSync(temp_repo)

        mock_run.return_value = Mock(returncode=0)

        result = sync._apply_stash(temp_repo, "stash@{0}")
        assert result is True

        mock_run.assert_called_once_with(
            ["git", "stash", "pop"], cwd=temp_repo, capture_output=True, text=True
        )

    @patch("subprocess.run")
    def test_apply_stash_failure(self, mock_run, temp_repo):
        """Test _apply_stash when application fails."""
        sync = WorktreeSync(temp_repo)

        mock_run.return_value = Mock(returncode=1)

        result = sync._apply_stash(temp_repo, "stash@{0}")
        assert result is False

    @patch("subprocess.run")
    def test_fetch_updates_success(self, mock_run, temp_repo):
        """Test _fetch_updates when fetch succeeds."""
        sync = WorktreeSync(temp_repo)

        mock_run.return_value = Mock(returncode=0)

        result = sync._fetch_updates(temp_repo, "origin")
        assert result is True

        mock_run.assert_called_once_with(
            ["git", "fetch", "origin", "--prune"], cwd=temp_repo, capture_output=True, text=True
        )

    @patch("subprocess.run")
    def test_fetch_updates_failure(self, mock_run, temp_repo):
        """Test _fetch_updates when fetch fails."""
        sync = WorktreeSync(temp_repo)

        mock_run.return_value = Mock(returncode=1)

        result = sync._fetch_updates(temp_repo, "origin")
        assert result is False

    @patch("subprocess.run")
    def test_check_divergence_up_to_date(self, mock_run, temp_repo):
        """Test _check_divergence when branch is up to date."""
        sync = WorktreeSync(temp_repo)

        mock_run.return_value = Mock(returncode=0, stdout="0\t0\n")

        result = sync._check_divergence(temp_repo, "origin", "main")
        assert result == "up-to-date"

    @patch("subprocess.run")
    def test_check_divergence_behind(self, mock_run, temp_repo):
        """Test _check_divergence when branch is behind."""
        sync = WorktreeSync(temp_repo)

        mock_run.return_value = Mock(returncode=0, stdout="2\t0\n")

        result = sync._check_divergence(temp_repo, "origin", "main")
        assert result == "behind"

    @patch("subprocess.run")
    def test_check_divergence_ahead(self, mock_run, temp_repo):
        """Test _check_divergence when branch is ahead."""
        sync = WorktreeSync(temp_repo)

        mock_run.return_value = Mock(returncode=0, stdout="0\t3\n")

        result = sync._check_divergence(temp_repo, "origin", "main")
        assert result == "ahead"

    @patch("subprocess.run")
    def test_check_divergence_diverged(self, mock_run, temp_repo):
        """Test _check_divergence when branch has diverged."""
        sync = WorktreeSync(temp_repo)

        mock_run.return_value = Mock(returncode=0, stdout="2\t3\n")

        result = sync._check_divergence(temp_repo, "origin", "main")
        assert result == "diverged"

    @patch("subprocess.run")
    def test_check_divergence_error(self, mock_run, temp_repo):
        """Test _check_divergence when git command fails."""
        sync = WorktreeSync(temp_repo)

        mock_run.return_value = Mock(returncode=1)

        result = sync._check_divergence(temp_repo, "origin", "main")
        assert result == "error"

    @patch("subprocess.run")
    def test_rebase_success(self, mock_run, temp_repo):
        """Test _rebase when rebase succeeds."""
        sync = WorktreeSync(temp_repo)

        mock_run.return_value = Mock(returncode=0)

        result = sync._rebase(temp_repo, "origin/main")
        assert result == {"success": True}

    @patch("subprocess.run")
    def test_rebase_conflict(self, mock_run, temp_repo):
        """Test _rebase when rebase has conflicts."""
        sync = WorktreeSync(temp_repo)

        mock_run.side_effect = [
            Mock(returncode=1),  # git rebase fails
            Mock(returncode=0, stdout="UU conflict.py\n"),  # git status shows conflicts
        ]

        result = sync._rebase(temp_repo, "origin/main")
        assert result == {"success": False, "conflict": True}

    @patch("subprocess.run")
    def test_rebase_failure(self, mock_run, temp_repo):
        """Test _rebase when rebase fails without conflicts."""
        sync = WorktreeSync(temp_repo)

        mock_run.side_effect = [
            Mock(returncode=1),  # git rebase fails
            Mock(returncode=0, stdout=""),  # git status shows no conflicts
        ]

        result = sync._rebase(temp_repo, "origin/main")
        assert result == {"success": False, "conflict": False}

    @patch("subprocess.run")
    def test_merge_success(self, mock_run, temp_repo):
        """Test _merge when merge succeeds."""
        sync = WorktreeSync(temp_repo)

        mock_run.return_value = Mock(returncode=0)

        result = sync._merge(temp_repo, "origin/main")
        assert result == {"success": True}

    @patch("subprocess.run")
    def test_merge_conflict(self, mock_run, temp_repo):
        """Test _merge when merge has conflicts."""
        sync = WorktreeSync(temp_repo)

        mock_run.side_effect = [
            Mock(returncode=1),  # git merge fails
            Mock(returncode=0, stdout="UU conflict.py\n"),  # git status shows conflicts
        ]

        result = sync._merge(temp_repo, "origin/main")
        assert result == {"success": False, "conflict": True}

    @patch("subprocess.run")
    def test_fast_forward_success(self, mock_run, temp_repo):
        """Test _fast_forward when fast-forward succeeds."""
        sync = WorktreeSync(temp_repo)

        mock_run.return_value = Mock(returncode=0)

        result = sync._fast_forward(temp_repo, "origin/main")
        assert result is True

    @patch("subprocess.run")
    def test_fast_forward_failure(self, mock_run, temp_repo):
        """Test _fast_forward when fast-forward fails."""
        sync = WorktreeSync(temp_repo)

        mock_run.return_value = Mock(returncode=1)

        result = sync._fast_forward(temp_repo, "origin/main")
        assert result is False

    @patch("subprocess.run")
    def test_get_conflicted_files_with_conflicts(self, mock_run, temp_repo):
        """Test _get_conflicted_files when conflicts exist."""
        sync = WorktreeSync(temp_repo)

        mock_run.return_value = Mock(returncode=0, stdout="file1.py\nfile2.py\n")

        result = sync._get_conflicted_files(temp_repo)
        assert result == ["file1.py", "file2.py"]

    @patch("subprocess.run")
    def test_get_conflicted_files_no_conflicts(self, mock_run, temp_repo):
        """Test _get_conflicted_files when no conflicts exist."""
        sync = WorktreeSync(temp_repo)

        mock_run.return_value = Mock(returncode=0, stdout="")

        result = sync._get_conflicted_files(temp_repo)
        assert result == []

    @patch("subprocess.run")
    def test_abort_rebase_success(self, mock_run, temp_repo):
        """Test abort_rebase when abort succeeds."""
        sync = WorktreeSync(temp_repo)

        mock_run.return_value = Mock(returncode=0)

        result = sync.abort_rebase(temp_repo)
        assert result is True

        mock_run.assert_called_once_with(
            ["git", "rebase", "--abort"], cwd=temp_repo, capture_output=True, text=True
        )

    @patch("subprocess.run")
    def test_abort_merge_success(self, mock_run, temp_repo):
        """Test abort_merge when abort succeeds."""
        sync = WorktreeSync(temp_repo)

        mock_run.return_value = Mock(returncode=0)

        result = sync.abort_merge(temp_repo)
        assert result is True

        mock_run.assert_called_once_with(
            ["git", "merge", "--abort"], cwd=temp_repo, capture_output=True, text=True
        )

    @patch("subprocess.run")
    def test_continue_rebase_success(self, mock_run, temp_repo):
        """Test continue_rebase when continue succeeds."""
        sync = WorktreeSync(temp_repo)

        mock_run.return_value = Mock(returncode=0)

        result = sync.continue_rebase(temp_repo)
        assert result is True

        mock_run.assert_called_once_with(
            ["git", "rebase", "--continue"], cwd=temp_repo, capture_output=True, text=True
        )

    def test_detect_conflicts(self, temp_repo):
        """Test detect_conflicts method."""
        sync = WorktreeSync(temp_repo)

        with patch.object(sync, "_get_conflicted_files") as mock_get_conflicts:
            mock_get_conflicts.return_value = ["file1.py", "file2.py"]

            has_conflicts, conflicts = sync.detect_conflicts(temp_repo)

            assert has_conflicts is True
            assert conflicts == ["file1.py", "file2.py"]
            mock_get_conflicts.assert_called_once_with(temp_repo.resolve())

    def test_detect_conflicts_none(self, temp_repo):
        """Test detect_conflicts when no conflicts exist."""
        sync = WorktreeSync(temp_repo)

        with patch.object(sync, "_get_conflicted_files") as mock_get_conflicts:
            mock_get_conflicts.return_value = []

            has_conflicts, conflicts = sync.detect_conflicts(temp_repo)

            assert has_conflicts is False
            assert conflicts == []


class TestWorktreeSyncIntegration:
    """Integration tests for sync method."""

    def test_sync_clean_repository(self, temp_repo):
        """Test sync with clean repository (up-to-date)."""
        sync = WorktreeSync(temp_repo)

        with (
            patch.object(sync, "_has_uncommitted_changes", return_value=False),
            patch.object(sync, "_fetch_updates", return_value=True),
            patch.object(sync, "_check_divergence", return_value="up-to-date"),
        ):

            result = sync.sync(temp_repo)

            assert result.status == SyncStatus.CLEAN
            assert result.worktree_path == temp_repo.resolve()
            assert result.message == "Sync completed successfully"

    def test_sync_fast_forward(self, temp_repo):
        """Test sync with fast-forward update."""
        sync = WorktreeSync(temp_repo)

        with (
            patch.object(sync, "_has_uncommitted_changes", return_value=False),
            patch.object(sync, "_fetch_updates", return_value=True),
            patch.object(sync, "_check_divergence", return_value="behind"),
            patch.object(sync, "_fast_forward", return_value=True),
        ):

            result = sync.sync(temp_repo)

            assert result.status == SyncStatus.UPDATED
            assert result.message == "Sync completed successfully"

    def test_sync_with_stash(self, temp_repo):
        """Test sync with uncommitted changes that need stashing."""
        sync = WorktreeSync(temp_repo)

        with (
            patch.object(sync, "_has_uncommitted_changes", side_effect=[True, False]),
            patch.object(sync, "_stash_changes", return_value="stash@{0}"),
            patch.object(sync, "_fetch_updates", return_value=True),
            patch.object(sync, "_check_divergence", return_value="up-to-date"),
            patch.object(sync, "_apply_stash", return_value=True),
        ):

            result = sync.sync(temp_repo)

            assert result.status == SyncStatus.CLEAN

    def test_sync_rebase_conflict(self, temp_repo):
        """Test sync with rebase conflicts."""
        sync = WorktreeSync(temp_repo)

        with (
            patch.object(sync, "_has_uncommitted_changes", return_value=False),
            patch.object(sync, "_fetch_updates", return_value=True),
            patch.object(sync, "_check_divergence", return_value="diverged"),
            patch.object(sync, "_rebase", return_value={"success": False, "conflict": True}),
            patch.object(sync, "_get_conflicted_files", return_value=["file.py"]),
        ):

            result = sync.sync(temp_repo, strategy="rebase")

            assert result.status == SyncStatus.CONFLICTS
            assert result.conflict_type == ConflictType.REBASE_CONFLICT
            assert result.conflicts == ["file.py"]

    def test_sync_merge_conflict(self, temp_repo):
        """Test sync with merge conflicts."""
        sync = WorktreeSync(temp_repo)

        with (
            patch.object(sync, "_has_uncommitted_changes", return_value=False),
            patch.object(sync, "_fetch_updates", return_value=True),
            patch.object(sync, "_check_divergence", return_value="diverged"),
            patch.object(sync, "_merge", return_value={"success": False, "conflict": True}),
            patch.object(sync, "_get_conflicted_files", return_value=["file.py"]),
        ):

            result = sync.sync(temp_repo, strategy="merge")

            assert result.status == SyncStatus.CONFLICTS
            assert result.conflict_type == ConflictType.MERGE_CONFLICT
            assert result.conflicts == ["file.py"]

    def test_sync_fetch_failure(self, temp_repo):
        """Test sync when fetch fails."""
        sync = WorktreeSync(temp_repo)

        with (
            patch.object(sync, "_has_uncommitted_changes", return_value=False),
            patch.object(sync, "_fetch_updates", return_value=False),
        ):

            result = sync.sync(temp_repo)

            assert result.status == SyncStatus.ERROR
            assert "Failed to fetch from origin" in result.message

    def test_sync_stash_failure(self, temp_repo):
        """Test sync when stashing fails."""
        sync = WorktreeSync(temp_repo)

        with (
            patch.object(sync, "_has_uncommitted_changes", return_value=True),
            patch.object(sync, "_stash_changes", return_value=None),
        ):

            result = sync.sync(temp_repo)

            assert result.status == SyncStatus.ERROR
            assert result.conflict_type == ConflictType.UNCOMMITTED_CHANGES
            assert "Failed to stash uncommitted changes" in result.message

    def test_sync_exception_handling(self, temp_repo):
        """Test sync exception handling."""
        sync = WorktreeSync(temp_repo)

        with patch.object(sync, "_has_uncommitted_changes", side_effect=Exception("Test error")):
            result = sync.sync(temp_repo)

            assert result.status == SyncStatus.ERROR
            assert "Test error" in result.message


class TestWorktreeSyncHelperMethods:
    """Tests for the new helper methods in WorktreeSync."""

    def test_handle_uncommitted_changes_no_changes(self, temp_repo):
        """Test _handle_uncommitted_changes when no changes exist."""
        sync = WorktreeSync(temp_repo)

        with patch.object(sync, "_has_uncommitted_changes", return_value=False):
            stash_ref, error_result = sync._handle_uncommitted_changes(temp_repo)

            assert stash_ref is None
            assert error_result is None

    def test_handle_uncommitted_changes_success(self, temp_repo):
        """Test _handle_uncommitted_changes when stashing succeeds."""
        sync = WorktreeSync(temp_repo)

        with (
            patch.object(sync, "_has_uncommitted_changes", return_value=True),
            patch.object(sync, "_stash_changes", return_value="stash@{0}"),
        ):

            stash_ref, error_result = sync._handle_uncommitted_changes(temp_repo)

            assert stash_ref == "stash@{0}"
            assert error_result is None

    def test_handle_uncommitted_changes_failure(self, temp_repo):
        """Test _handle_uncommitted_changes when stashing fails."""
        sync = WorktreeSync(temp_repo)

        with (
            patch.object(sync, "_has_uncommitted_changes", return_value=True),
            patch.object(sync, "_stash_changes", return_value=None),
        ):

            stash_ref, error_result = sync._handle_uncommitted_changes(temp_repo)

            assert stash_ref is None
            assert error_result is not None
            assert error_result.status == SyncStatus.ERROR
            assert error_result.conflict_type == ConflictType.UNCOMMITTED_CHANGES

    def test_perform_diverged_sync_rebase_success(self, temp_repo):
        """Test _perform_diverged_sync with successful rebase."""
        sync = WorktreeSync(temp_repo)

        with patch.object(sync, "_rebase", return_value={"success": True}):
            result = sync._perform_diverged_sync(temp_repo, "origin", "main", "rebase", None)

            assert result is None  # No error means success

    def test_perform_diverged_sync_rebase_conflict(self, temp_repo):
        """Test _perform_diverged_sync with rebase conflict."""
        sync = WorktreeSync(temp_repo)

        with (
            patch.object(sync, "_rebase", return_value={"success": False}),
            patch.object(sync, "_get_conflicted_files", return_value=["file.py"]),
        ):

            result = sync._perform_diverged_sync(temp_repo, "origin", "main", "rebase", "stash@{0}")

            assert result is not None
            assert result.status == SyncStatus.CONFLICTS
            assert result.conflict_type == ConflictType.REBASE_CONFLICT
            assert result.conflicts == ["file.py"]
            assert result.stash_ref == "stash@{0}"

    def test_perform_diverged_sync_merge_success(self, temp_repo):
        """Test _perform_diverged_sync with successful merge."""
        sync = WorktreeSync(temp_repo)

        with patch.object(sync, "_merge", return_value={"success": True}):
            result = sync._perform_diverged_sync(temp_repo, "origin", "main", "merge", None)

            assert result is None  # No error means success

    def test_perform_diverged_sync_merge_conflict(self, temp_repo):
        """Test _perform_diverged_sync with merge conflict."""
        sync = WorktreeSync(temp_repo)

        with (
            patch.object(sync, "_merge", return_value={"success": False}),
            patch.object(sync, "_get_conflicted_files", return_value=["file.py"]),
        ):

            result = sync._perform_diverged_sync(temp_repo, "origin", "main", "merge", None)

            assert result is not None
            assert result.status == SyncStatus.CONFLICTS
            assert result.conflict_type == ConflictType.MERGE_CONFLICT
            assert result.conflicts == ["file.py"]

    def test_restore_stashed_changes_success(self, temp_repo):
        """Test _restore_stashed_changes when successful."""
        sync = WorktreeSync(temp_repo)

        with patch.object(sync, "_apply_stash", return_value=True):
            result = sync._restore_stashed_changes(temp_repo, "stash@{0}")

            assert result is None  # No error means success

    def test_restore_stashed_changes_conflict(self, temp_repo):
        """Test _restore_stashed_changes when there's a conflict."""
        sync = WorktreeSync(temp_repo)

        with patch.object(sync, "_apply_stash", return_value=False):
            result = sync._restore_stashed_changes(temp_repo, "stash@{0}")

            assert result is not None
            assert result.status == SyncStatus.CONFLICTS
            assert result.conflict_type == ConflictType.MERGE_CONFLICT
            assert result.stash_ref == "stash@{0}"

    def test_determine_final_status_with_changes(self, temp_repo):
        """Test _determine_final_status when there are uncommitted changes."""
        sync = WorktreeSync(temp_repo)

        with patch.object(sync, "_has_uncommitted_changes", return_value=True):
            result = sync._determine_final_status(temp_repo, "behind", "stash@{0}")

            assert result.status == SyncStatus.STASHED
            assert result.stash_ref == "stash@{0}"
            assert "uncommitted changes" in result.message

    def test_determine_final_status_clean_updated(self, temp_repo):
        """Test _determine_final_status when clean and updated."""
        sync = WorktreeSync(temp_repo)

        with patch.object(sync, "_has_uncommitted_changes", return_value=False):
            result = sync._determine_final_status(temp_repo, "behind", None)

            assert result.status == SyncStatus.UPDATED
            assert result.message == "Sync completed successfully"

    def test_determine_final_status_clean_up_to_date(self, temp_repo):
        """Test _determine_final_status when clean and up-to-date."""
        sync = WorktreeSync(temp_repo)

        with patch.object(sync, "_has_uncommitted_changes", return_value=False):
            result = sync._determine_final_status(temp_repo, "up-to-date", None)

            assert result.status == SyncStatus.CLEAN
            assert result.message == "Sync completed successfully"
