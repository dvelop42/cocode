"""Ready marker watcher for monitoring agent completion.

This module provides utilities for monitoring git commits to detect when
agents have signaled completion via the ready marker.
"""

import logging
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)


class ReadyMarkerWatcher:
    """Watches for ready markers in git commits with efficient polling."""

    def __init__(
        self,
        worktree_path: Path,
        ready_marker: str = "cocode ready for check",
        initial_delay: float = 0.5,
        max_delay: float = 5.0,
        backoff_factor: float = 1.5,
    ):
        """Initialize the ready marker watcher.

        Args:
            worktree_path: Path to the git worktree to monitor
            ready_marker: The marker string to search for in commits
            initial_delay: Initial polling delay in seconds
            max_delay: Maximum polling delay in seconds
            backoff_factor: Factor to increase delay on each iteration
        """
        self.worktree_path = worktree_path
        self.ready_marker = ready_marker
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self._last_commit_hash: str | None = None

    def check_ready(self) -> bool:
        """Check if the ready marker is present in the latest commit.

        Returns:
            True if ready marker found, False otherwise
        """
        try:
            # Get the full commit message including multiline body
            result = subprocess.run(
                ["git", "log", "-1", "--format=%B"],
                cwd=self.worktree_path,
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                logger.debug(f"Failed to get commit message: {result.stderr}")
                return False

            commit_message = result.stdout.strip()
            is_ready = self.ready_marker in commit_message

            if is_ready:
                logger.info(f"Ready marker found in commit at {self.worktree_path}")

            return is_ready

        except Exception as e:
            logger.error(f"Error checking for ready marker: {e}")
            return False

    def get_latest_commit_hash(self) -> str | None:
        """Get the hash of the latest commit.

        Returns:
            Commit hash string or None if no commits
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.worktree_path,
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                return None

            return result.stdout.strip()

        except Exception:
            return None

    def has_new_commit(self) -> bool:
        """Check if there's a new commit since last check.

        Returns:
            True if new commit detected, False otherwise
        """
        current_hash = self.get_latest_commit_hash()

        if current_hash is None:
            return False

        if self._last_commit_hash is None:
            self._last_commit_hash = current_hash
            return True

        if current_hash != self._last_commit_hash:
            self._last_commit_hash = current_hash
            return True

        return False

    def watch(
        self,
        timeout: float | None = None,
        callback: Callable[[bool], None] | None = None,
        check_interval_callback: Callable[[float], None] | None = None,
    ) -> bool:
        """Watch for ready marker with exponential backoff polling.

        Args:
            timeout: Maximum time to wait in seconds (None for infinite)
            callback: Optional callback when new commit detected (passed ready status)
            check_interval_callback: Optional callback before each check (passed current delay)

        Returns:
            True if ready marker found, False if timeout reached
        """
        start_time = time.time()
        delay = self.initial_delay

        logger.debug(f"Starting ready marker watch for {self.worktree_path}")

        while True:
            # Check timeout
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    logger.debug(f"Ready marker watch timed out after {elapsed:.1f}s")
                    return False

            # Notify about check interval if callback provided
            if check_interval_callback:
                check_interval_callback(delay)

            # Check for new commit
            if self.has_new_commit():
                is_ready = self.check_ready()

                if callback:
                    callback(is_ready)

                if is_ready:
                    return True

                # Reset delay on new commit (agent is active)
                delay = self.initial_delay
            else:
                # Increase delay with exponential backoff
                delay = min(delay * self.backoff_factor, self.max_delay)

            # Wait before next check
            if timeout is not None:
                remaining = timeout - (time.time() - start_time)
                sleep_time = min(delay, remaining)
                if sleep_time <= 0:
                    continue
            else:
                sleep_time = delay

            logger.debug(f"Waiting {sleep_time:.1f}s before next check")
            time.sleep(sleep_time)

    def watch_continuous(
        self,
        callback: Callable[[bool], None],
        check_interval_callback: Callable[[float], None] | None = None,
    ) -> None:
        """Continuously watch for ready markers without timeout.

        Args:
            callback: Callback when new commit detected (passed ready status)
            check_interval_callback: Optional callback before each check (passed current delay)

        Note:
            This method runs indefinitely until interrupted.
        """
        self.watch(timeout=None, callback=callback, check_interval_callback=check_interval_callback)


def check_ready_in_worktree(
    worktree_path: Path, ready_marker: str = "cocode ready for check"
) -> bool:
    """Quick check if ready marker exists in the latest commit of a worktree.

    Args:
        worktree_path: Path to git worktree
        ready_marker: Marker string to search for

    Returns:
        True if ready marker found, False otherwise
    """
    watcher = ReadyMarkerWatcher(worktree_path, ready_marker)
    return watcher.check_ready()
