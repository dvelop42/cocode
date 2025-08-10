"""Worktree synchronization with conflict detection."""

import logging
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class SyncStatus(Enum):
    """Status of a sync operation."""

    CLEAN = "clean"
    UPDATED = "updated"
    CONFLICTS = "conflicts"
    STASHED = "stashed"
    ERROR = "error"


class ConflictType(Enum):
    """Types of conflicts that can occur."""

    MERGE_CONFLICT = "merge_conflict"
    REBASE_CONFLICT = "rebase_conflict"
    UNCOMMITTED_CHANGES = "uncommitted_changes"
    DIVERGED = "diverged"


@dataclass
class SyncResult:
    """Result of a sync operation."""

    status: SyncStatus
    worktree_path: Path
    conflicts: list[str] = None
    conflict_type: ConflictType | None = None
    stash_ref: str | None = None
    message: str = ""


class WorktreeSync:
    """Handle worktree synchronization with upstream changes."""

    STASH_MESSAGE = "cocode: auto-stash before sync"

    def __init__(self, repo_path: Path):
        """Initialize worktree sync.

        Args:
            repo_path: Path to the repository
        """
        self.repo_path = Path(repo_path).resolve()

    def sync(
        self,
        worktree_path: Path,
        remote: str = "origin",
        base_branch: str = "main",
        strategy: str = "rebase",
    ) -> SyncResult:
        """Sync a worktree with upstream changes.

        Args:
            worktree_path: Path to the worktree
            remote: Remote name to sync with
            base_branch: Base branch to sync against
            strategy: Sync strategy ('rebase' or 'merge')

        Returns:
            SyncResult with sync status and details
        """
        worktree_path = Path(worktree_path).resolve()

        try:
            # Handle uncommitted changes
            stash_ref, error_result = self._handle_uncommitted_changes(worktree_path)
            if error_result:
                return error_result

            # Fetch latest changes
            if not self._fetch_updates(worktree_path, remote):
                return SyncResult(
                    status=SyncStatus.ERROR,
                    worktree_path=worktree_path,
                    message=f"Failed to fetch from {remote}",
                )

            # Check if branch has diverged
            divergence = self._check_divergence(worktree_path, remote, base_branch)

            if divergence == "diverged":
                # Perform sync for diverged branches
                conflict_result = self._perform_diverged_sync(
                    worktree_path, remote, base_branch, strategy, stash_ref
                )
                if conflict_result:
                    return conflict_result

            elif divergence == "behind":
                # Fast-forward merge
                if not self._fast_forward(worktree_path, f"{remote}/{base_branch}"):
                    return SyncResult(
                        status=SyncStatus.ERROR,
                        worktree_path=worktree_path,
                        message="Failed to fast-forward merge",
                    )

            # Restore stashed changes if any
            if stash_ref:
                conflict_result = self._restore_stashed_changes(worktree_path, stash_ref)
                if conflict_result:
                    return conflict_result

            # Determine final status
            return self._determine_final_status(worktree_path, divergence, stash_ref)

        except Exception as e:
            logger.error(f"Sync error for {worktree_path}: {e}")
            return SyncResult(status=SyncStatus.ERROR, worktree_path=worktree_path, message=str(e))

    def _handle_uncommitted_changes(
        self, worktree_path: Path
    ) -> tuple[str | None, SyncResult | None]:
        """Handle uncommitted changes by stashing them.

        Args:
            worktree_path: Path to the worktree

        Returns:
            Tuple of (stash_ref, error_result). If error_result is not None, sync should return it.
        """
        if not self._has_uncommitted_changes(worktree_path):
            return None, None

        stash_ref = self._stash_changes(worktree_path)
        if not stash_ref:
            return None, SyncResult(
                status=SyncStatus.ERROR,
                worktree_path=worktree_path,
                conflict_type=ConflictType.UNCOMMITTED_CHANGES,
                message="Failed to stash uncommitted changes",
            )

        logger.info(f"Stashed changes in {worktree_path}: {stash_ref}")
        return stash_ref, None

    def _perform_diverged_sync(
        self,
        worktree_path: Path,
        remote: str,
        base_branch: str,
        strategy: str,
        stash_ref: str | None,
    ) -> SyncResult | None:
        """Perform synchronization when branch has diverged.

        Args:
            worktree_path: Path to the worktree
            remote: Remote name
            base_branch: Base branch name
            strategy: Sync strategy ('rebase' or 'merge')
            stash_ref: Reference to stashed changes if any

        Returns:
            SyncResult if there was an error or conflict, None if successful
        """
        target_branch = f"{remote}/{base_branch}"

        if strategy == "rebase":
            result = self._rebase(worktree_path, target_branch)
        else:
            result = self._merge(worktree_path, target_branch)

        if not result["success"]:
            conflicts = self._get_conflicted_files(worktree_path)
            return SyncResult(
                status=SyncStatus.CONFLICTS,
                worktree_path=worktree_path,
                conflicts=conflicts,
                conflict_type=(
                    ConflictType.REBASE_CONFLICT
                    if strategy == "rebase"
                    else ConflictType.MERGE_CONFLICT
                ),
                stash_ref=stash_ref,
                message=f"{strategy.capitalize()} resulted in conflicts",
            )
        return None

    def _restore_stashed_changes(self, worktree_path: Path, stash_ref: str) -> SyncResult | None:
        """Restore stashed changes and handle any conflicts.

        Args:
            worktree_path: Path to the worktree
            stash_ref: Reference to stashed changes

        Returns:
            SyncResult if there was a conflict, None if successful
        """
        if not self._apply_stash(worktree_path, stash_ref):
            return SyncResult(
                status=SyncStatus.CONFLICTS,
                worktree_path=worktree_path,
                conflict_type=ConflictType.MERGE_CONFLICT,
                stash_ref=stash_ref,
                message="Conflicts when applying stashed changes",
            )
        return None

    def _determine_final_status(
        self, worktree_path: Path, divergence: str, stash_ref: str | None
    ) -> SyncResult:
        """Determine the final sync status and create result.

        Args:
            worktree_path: Path to the worktree
            divergence: Divergence status from _check_divergence
            stash_ref: Reference to stashed changes if any

        Returns:
            Final SyncResult
        """
        if self._has_uncommitted_changes(worktree_path):
            return SyncResult(
                status=SyncStatus.STASHED,
                worktree_path=worktree_path,
                stash_ref=stash_ref,
                message="Sync completed with uncommitted changes",
            )
        else:
            status = SyncStatus.UPDATED if divergence != "up-to-date" else SyncStatus.CLEAN
            return SyncResult(
                status=status,
                worktree_path=worktree_path,
                message="Sync completed successfully",
            )

    def detect_conflicts(self, worktree_path: Path) -> tuple[bool, list[str]]:
        """Detect if a worktree has merge conflicts.

        Args:
            worktree_path: Path to the worktree

        Returns:
            Tuple of (has_conflicts, list_of_conflicted_files)
        """
        worktree_path = Path(worktree_path).resolve()
        conflicts = self._get_conflicted_files(worktree_path)
        return bool(conflicts), conflicts

    def _has_uncommitted_changes(self, worktree_path: Path) -> bool:
        """Check if worktree has uncommitted changes."""
        result = subprocess.run(
            ["git", "status", "--porcelain"], cwd=worktree_path, capture_output=True, text=True
        )
        return bool(result.stdout.strip())

    def _stash_changes(self, worktree_path: Path) -> str | None:
        """Stash uncommitted changes."""
        result = subprocess.run(
            ["git", "stash", "push", "-m", self.STASH_MESSAGE],
            cwd=worktree_path,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            # Get stash ref
            stash_result = subprocess.run(
                ["git", "rev-parse", "stash@{0}"], cwd=worktree_path, capture_output=True, text=True
            )
            return stash_result.stdout.strip() if stash_result.returncode == 0 else None
        return None

    def _apply_stash(self, worktree_path: Path, stash_ref: str) -> bool:
        """Apply stashed changes."""
        result = subprocess.run(
            ["git", "stash", "pop"], cwd=worktree_path, capture_output=True, text=True
        )
        return result.returncode == 0

    def _fetch_updates(self, worktree_path: Path, remote: str) -> bool:
        """Fetch updates from remote."""
        result = subprocess.run(
            ["git", "fetch", remote, "--prune"], cwd=worktree_path, capture_output=True, text=True
        )
        return result.returncode == 0

    def _check_divergence(self, worktree_path: Path, remote: str, branch: str) -> str:
        """Check if branch has diverged from remote.

        Returns:
            'ahead', 'behind', 'diverged', or 'up-to-date'
        """
        # Check ahead/behind status
        result = subprocess.run(
            ["git", "rev-list", "--left-right", "--count", f"{remote}/{branch}...HEAD"],
            cwd=worktree_path,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return "error"

        parts = result.stdout.strip().split()
        if len(parts) != 2:
            return "error"

        behind, ahead = int(parts[0]), int(parts[1])

        if behind == 0 and ahead == 0:
            return "up-to-date"
        elif behind > 0 and ahead == 0:
            return "behind"
        elif behind == 0 and ahead > 0:
            return "ahead"
        else:
            return "diverged"

    def _rebase(self, worktree_path: Path, onto: str) -> dict:
        """Rebase current branch onto target."""
        result = subprocess.run(
            ["git", "rebase", onto], cwd=worktree_path, capture_output=True, text=True
        )

        if result.returncode != 0:
            # Check if it's a conflict
            status = subprocess.run(
                ["git", "status", "--porcelain"], cwd=worktree_path, capture_output=True, text=True
            )

            if "UU" in status.stdout or "AA" in status.stdout:
                return {"success": False, "conflict": True}
            return {"success": False, "conflict": False}

        return {"success": True}

    def _merge(self, worktree_path: Path, branch: str) -> dict:
        """Merge branch into current branch."""
        result = subprocess.run(
            ["git", "merge", branch], cwd=worktree_path, capture_output=True, text=True
        )

        if result.returncode != 0:
            # Check if it's a conflict
            status = subprocess.run(
                ["git", "status", "--porcelain"], cwd=worktree_path, capture_output=True, text=True
            )

            if "UU" in status.stdout or "AA" in status.stdout:
                return {"success": False, "conflict": True}
            return {"success": False, "conflict": False}

        return {"success": True}

    def _fast_forward(self, worktree_path: Path, branch: str) -> bool:
        """Fast-forward merge to branch."""
        result = subprocess.run(
            ["git", "merge", "--ff-only", branch], cwd=worktree_path, capture_output=True, text=True
        )
        return result.returncode == 0

    def _get_conflicted_files(self, worktree_path: Path) -> list[str]:
        """Get list of files with merge conflicts."""
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=U"],
            cwd=worktree_path,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0 and result.stdout:
            return result.stdout.strip().split("\n")
        return []

    def abort_rebase(self, worktree_path: Path) -> bool:
        """Abort an ongoing rebase."""
        result = subprocess.run(
            ["git", "rebase", "--abort"], cwd=worktree_path, capture_output=True, text=True
        )
        return result.returncode == 0

    def abort_merge(self, worktree_path: Path) -> bool:
        """Abort an ongoing merge."""
        result = subprocess.run(
            ["git", "merge", "--abort"], cwd=worktree_path, capture_output=True, text=True
        )
        return result.returncode == 0

    def continue_rebase(self, worktree_path: Path) -> bool:
        """Continue a rebase after resolving conflicts."""
        result = subprocess.run(
            ["git", "rebase", "--continue"], cwd=worktree_path, capture_output=True, text=True
        )
        return result.returncode == 0
