"""Default agent implementations."""

import logging
from pathlib import Path

from cocode.agents.base import Agent
from cocode.agents.ready_watcher import check_ready_in_worktree

logger = logging.getLogger(__name__)


class GitBasedAgent(Agent):
    """Base agent that uses git commits for ready detection.

    This provides a default implementation of check_ready that looks for
    the ready marker in git commits, which is the standard protocol.
    """

    def check_ready(self, worktree_path: Path) -> bool:
        """Check if agent has signaled it's ready via git commit.

        Args:
            worktree_path: Path to the git worktree

        Returns:
            True if ready marker found in latest commit
        """
        return check_ready_in_worktree(worktree_path, "cocode ready for check")
