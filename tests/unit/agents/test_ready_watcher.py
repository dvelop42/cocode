"""Tests for ready marker watcher."""

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from cocode.agents.ready_watcher import ReadyMarkerWatcher, check_ready_in_worktree


class TestReadyMarkerWatcher:
    """Test the ReadyMarkerWatcher class."""

    def test_init(self, tmp_path: Path):
        """Test watcher initialization."""
        watcher = ReadyMarkerWatcher(
            worktree_path=tmp_path,
            ready_marker="custom marker",
            initial_delay=1.0,
            max_delay=10.0,
            backoff_factor=2.0,
        )

        assert watcher.worktree_path == tmp_path
        assert watcher.ready_marker == "custom marker"
        assert watcher.initial_delay == 1.0
        assert watcher.max_delay == 10.0
        assert watcher.backoff_factor == 2.0
        assert watcher._last_commit_hash is None

    def test_check_ready_with_marker(self, tmp_path: Path):
        """Test checking for ready marker when present."""
        watcher = ReadyMarkerWatcher(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="fix: issue #123\n\ncocode ready for check\n"
            )

            assert watcher.check_ready() is True

            mock_run.assert_called_once_with(
                ["git", "log", "-1", "--format=%B"],
                cwd=tmp_path,
                capture_output=True,
                text=True,
                check=False,
            )

    def test_check_ready_without_marker(self, tmp_path: Path):
        """Test checking for ready marker when not present."""
        watcher = ReadyMarkerWatcher(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="fix: issue #123\n\nNo marker here\n"
            )

            assert watcher.check_ready() is False

    def test_check_ready_git_error(self, tmp_path: Path):
        """Test check_ready when git command fails."""
        watcher = ReadyMarkerWatcher(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="fatal: not a git repository")

            assert watcher.check_ready() is False

    def test_check_ready_exception(self, tmp_path: Path):
        """Test check_ready when exception occurs."""
        watcher = ReadyMarkerWatcher(tmp_path)

        with patch("subprocess.run", side_effect=Exception("Test error")):
            assert watcher.check_ready() is False

    def test_get_latest_commit_hash(self, tmp_path: Path):
        """Test getting latest commit hash."""
        watcher = ReadyMarkerWatcher(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="abc123def456\n")

            assert watcher.get_latest_commit_hash() == "abc123def456"

            mock_run.assert_called_once_with(
                ["git", "rev-parse", "HEAD"],
                cwd=tmp_path,
                capture_output=True,
                text=True,
                check=False,
            )

    def test_get_latest_commit_hash_no_commits(self, tmp_path: Path):
        """Test getting commit hash when no commits exist."""
        watcher = ReadyMarkerWatcher(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)

            assert watcher.get_latest_commit_hash() is None

    def test_get_latest_commit_hash_exception(self, tmp_path: Path):
        """Exception while fetching commit hash returns None."""
        watcher = ReadyMarkerWatcher(tmp_path)

        with patch("subprocess.run", side_effect=Exception("boom")):
            assert watcher.get_latest_commit_hash() is None

    def test_has_new_commit_first_check(self, tmp_path: Path):
        """Test has_new_commit on first check."""
        watcher = ReadyMarkerWatcher(tmp_path)

        with patch.object(watcher, "get_latest_commit_hash", return_value="abc123"):
            assert watcher.has_new_commit() is True
            assert watcher._last_commit_hash == "abc123"

    def test_has_new_commit_no_change(self, tmp_path: Path):
        """Test has_new_commit when commit hasn't changed."""
        watcher = ReadyMarkerWatcher(tmp_path)
        watcher._last_commit_hash = "abc123"

        with patch.object(watcher, "get_latest_commit_hash", return_value="abc123"):
            assert watcher.has_new_commit() is False

    def test_has_new_commit_new_commit(self, tmp_path: Path):
        """Test has_new_commit when new commit exists."""
        watcher = ReadyMarkerWatcher(tmp_path)
        watcher._last_commit_hash = "abc123"

        with patch.object(watcher, "get_latest_commit_hash", return_value="def456"):
            assert watcher.has_new_commit() is True
            assert watcher._last_commit_hash == "def456"

    def test_has_new_commit_no_commits(self, tmp_path: Path):
        """Test has_new_commit when no commits exist."""
        watcher = ReadyMarkerWatcher(tmp_path)

        with patch.object(watcher, "get_latest_commit_hash", return_value=None):
            assert watcher.has_new_commit() is False

    def test_watch_immediate_ready(self, tmp_path: Path):
        """Test watch when ready marker is immediately found."""
        watcher = ReadyMarkerWatcher(tmp_path)

        with patch.object(watcher, "has_new_commit", return_value=True):
            with patch.object(watcher, "check_ready", return_value=True):
                callback = MagicMock()

                result = watcher.watch(timeout=10, callback=callback)

                assert result is True
                callback.assert_called_once_with(True)

    def test_watch_timeout(self, tmp_path: Path):
        """Test watch timeout."""
        watcher = ReadyMarkerWatcher(tmp_path, initial_delay=0.1)

        with patch.object(watcher, "has_new_commit", return_value=False):
            with patch("time.sleep"):  # Speed up test
                result = watcher.watch(timeout=0.05)

                assert result is False

    def test_watch_with_new_commits(self, tmp_path: Path):
        """Test watch with multiple new commits before ready."""
        watcher = ReadyMarkerWatcher(tmp_path, initial_delay=0.1)

        # Simulate: no commit, new commit (not ready), new commit (ready)
        has_new_commit_results = [False, True, True]
        check_ready_results = [False, True]

        with patch.object(watcher, "has_new_commit", side_effect=has_new_commit_results):
            with patch.object(watcher, "check_ready", side_effect=check_ready_results):
                with patch("time.sleep"):  # Speed up test
                    callback = MagicMock()

                    result = watcher.watch(timeout=10, callback=callback)

                    assert result is True
                    # The callback is called with the result of check_ready
                    # Filter out __bool__ calls that may occur
                    actual_calls = [c for c in callback.call_args_list if c != call.__bool__()]
                    assert len(actual_calls) == 2
                    assert actual_calls == [call(False), call(True)]

    def test_watch_exponential_backoff(self, tmp_path: Path):
        """Test exponential backoff in watch."""
        watcher = ReadyMarkerWatcher(tmp_path, initial_delay=0.5, max_delay=2.0, backoff_factor=2.0)

        sleep_times = []
        check_count = 0

        def mock_has_new():
            nonlocal check_count
            check_count += 1
            # Stop after enough iterations to see the pattern
            if check_count > 4:
                raise KeyboardInterrupt()
            return False

        def track_sleep(duration):
            sleep_times.append(duration)

        with patch.object(watcher, "has_new_commit", side_effect=mock_has_new):
            with patch("time.sleep", side_effect=track_sleep):
                with pytest.raises(KeyboardInterrupt):
                    watcher.watch(timeout=None)

        # After first check with no new commit, delay starts at initial_delay and increases
        assert len(sleep_times) >= 3
        # First sleep is initial_delay * backoff_factor since no new commit was found
        assert sleep_times[0] == pytest.approx(0.5 * 2.0)  # 1.0
        assert sleep_times[1] == pytest.approx(1.0 * 2.0)  # 2.0
        assert sleep_times[2] == pytest.approx(2.0)  # Capped at max_delay

    def test_watch_reset_delay_on_new_commit(self, tmp_path: Path):
        """Test that delay resets when new commit is detected."""
        watcher = ReadyMarkerWatcher(tmp_path, initial_delay=0.5, backoff_factor=2.0)

        has_new_results = [False, False, True, False]
        iteration = 0
        sleep_times = []

        def mock_has_new():
            nonlocal iteration
            if iteration < len(has_new_results):
                result = has_new_results[iteration]
                iteration += 1
                return result
            raise KeyboardInterrupt()

        def track_sleep(duration):
            sleep_times.append(duration)

        with patch.object(watcher, "has_new_commit", side_effect=mock_has_new):
            with patch.object(watcher, "check_ready", return_value=False):
                with patch("time.sleep", side_effect=track_sleep):
                    with pytest.raises(KeyboardInterrupt):
                        watcher.watch(timeout=None)

        # After no new commit, delay increases with backoff
        # After new commit is detected, delay resets to initial_delay
        assert len(sleep_times) >= 3
        assert sleep_times[0] == pytest.approx(1.0)  # initial_delay * backoff after first False
        assert sleep_times[1] == pytest.approx(2.0)  # previous * backoff after second False
        assert sleep_times[2] == pytest.approx(0.5)  # Reset to initial_delay after new commit

    def test_watch_continuous(self, tmp_path: Path):
        """Test continuous watching."""
        watcher = ReadyMarkerWatcher(tmp_path)

        # Mock watch to stop after one iteration
        with patch.object(watcher, "watch") as mock_watch:
            callback = MagicMock()
            interval_callback = MagicMock()

            watcher.watch_continuous(callback, interval_callback)

            mock_watch.assert_called_once_with(
                timeout=None, callback=callback, check_interval_callback=interval_callback
            )

    def test_check_interval_callback(self, tmp_path: Path):
        """Test that check interval callback is called."""
        watcher = ReadyMarkerWatcher(tmp_path, initial_delay=0.1)

        intervals = []

        def track_interval(delay):
            intervals.append(delay)
            if len(intervals) >= 3:
                raise KeyboardInterrupt()

        with patch.object(watcher, "has_new_commit", return_value=False):
            with patch("time.sleep"):
                with pytest.raises(KeyboardInterrupt):
                    watcher.watch(timeout=None, check_interval_callback=track_interval)

        assert len(intervals) == 3
        # Verify intervals follow backoff pattern
        assert intervals[0] == pytest.approx(0.1)
        assert intervals[1] > intervals[0]
        assert intervals[2] > intervals[1]


def test_check_ready_in_worktree(tmp_path: Path):
    """Test the convenience function check_ready_in_worktree."""
    with patch("cocode.agents.ready_watcher.ReadyMarkerWatcher") as mock_watcher_class:
        mock_instance = MagicMock()
        mock_instance.check_ready.return_value = True
        mock_watcher_class.return_value = mock_instance

        result = check_ready_in_worktree(tmp_path, "custom marker")

        assert result is True
        mock_watcher_class.assert_called_once_with(tmp_path, "custom marker")
        mock_instance.check_ready.assert_called_once()


def test_check_ready_in_worktree_default_marker(tmp_path: Path):
    """Test check_ready_in_worktree with default marker."""
    with patch("cocode.agents.ready_watcher.ReadyMarkerWatcher") as mock_watcher_class:
        mock_instance = MagicMock()
        mock_instance.check_ready.return_value = False
        mock_watcher_class.return_value = mock_instance

        result = check_ready_in_worktree(tmp_path)

        assert result is False
        mock_watcher_class.assert_called_once_with(tmp_path, "cocode ready for check")
