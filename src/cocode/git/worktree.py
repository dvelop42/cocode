"""Git worktree management."""

import logging
import re
import shutil
import subprocess
from pathlib import Path

from cocode.git.sync import SyncResult, SyncStatus, WorktreeSync

logger = logging.getLogger(__name__)


class WorktreeError(Exception):
    """Raised when worktree operations fail."""

    pass


class WorktreeManager:
    """Manages git worktrees for agents."""

    COCODE_PREFIX = "cocode_"

    def __init__(self, repo_path: Path, dry_run: bool = False):
        """Initialize worktree manager.

        Args:
            repo_path: Path to the main repository
            dry_run: If True, preview operations without executing them
        """
        self.repo_path = Path(repo_path).resolve()
        self.dry_run = dry_run
        self._validate_git_repo()
        self.sync = WorktreeSync(self.repo_path)

    def _validate_git_repo(self) -> None:
        """Validate that repo_path is a git repository."""
        git_dir = self.repo_path / ".git"
        if not git_dir.exists():
            raise WorktreeError(f"Not a git repository: {self.repo_path}")

    def _validate_worktree_path(self, path: Path) -> bool:
        """Ensure worktree path is within safe boundaries.

        Args:
            path: Path to validate

        Returns:
            True if path is safe, False otherwise
        """
        try:
            resolved_path = path.resolve()
            allowed_parent = self.repo_path.parent.resolve()
            # Allow any path under the repo's parent directory
            return resolved_path.is_relative_to(allowed_parent)
        except (ValueError, RuntimeError):
            return False

    def _validate_agent_name(self, agent_name: str) -> str:
        """Validate and sanitize agent name.

        Args:
            agent_name: Name to validate

        Returns:
            Sanitized agent name

        Raises:
            WorktreeError: If agent name is invalid
        """
        # First check if the name contains only allowed characters
        if not agent_name:
            raise WorktreeError("Agent name cannot be empty")

        # Check for path traversal attempts
        if ".." in agent_name or "/" in agent_name or "\\" in agent_name:
            raise WorktreeError(f"Invalid agent name: {agent_name} (contains path separators)")

        # Sanitize the name
        safe_agent_name = re.sub(r"[^a-zA-Z0-9_-]", "_", agent_name)

        # Final validation - ensure it only contains allowed characters
        if not re.match(r"^[a-zA-Z0-9_-]+$", safe_agent_name):
            raise WorktreeError(f"Invalid agent name after sanitization: {safe_agent_name}")

        return safe_agent_name

    def _run_git_command(self, args: list[str], cwd: Path | None = None) -> str:
        """Run a git command and return output.

        Args:
            args: Git command arguments
            cwd: Working directory for command (defaults to repo_path)

        Returns:
            Command output

        Raises:
            WorktreeError: If git command fails
        """
        if cwd is None:
            cwd = self.repo_path

        cmd = ["git"] + args

        if self.dry_run and self._is_write_command(args):
            # In dry run mode, don't execute write commands
            logger.info(f"[DRY RUN] Would execute: {' '.join(cmd)}")
            return "[DRY RUN]"

        try:
            result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.error(f"Git command failed: {' '.join(cmd)}")
            logger.error(f"Error: {e.stderr}")
            raise WorktreeError(f"Git command failed: {e.stderr}") from e
        except FileNotFoundError:
            raise WorktreeError("Git is not installed or not in PATH") from None

    def _is_write_command(self, args: list[str]) -> bool:
        """Heuristically determine if a git command is read-only.

        In dry-run mode we default to treating commands as write operations
        unless they are explicitly known to be read-only. This reduces the
        chance of missing a new mutating git verb.
        """
        if not args:
            return False

        verb = args[0]

        # Explicitly allow common read-only commands
        read_only_verbs = {
            "status",
            "log",
            "show",
            "diff",
            "rev-parse",
            "symbolic-ref",
        }

        if verb in read_only_verbs:
            return False

        # Allow specific read-only subcommands
        if verb == "worktree" and len(args) >= 2 and args[1] == "list":
            return False

        if verb == "branch" and (
            len(args) == 1 or args[1] in {"--list", "-v", "-vv", "--show-current"}
        ):
            return False

        # Treat all others as potentially mutating
        return True

    def _compute_worktree_path(self, agent_name: str) -> Path:
        """Compute and validate worktree path for an agent."""
        safe_agent_name = self._validate_agent_name(agent_name)
        worktree_dir_name = f"{self.COCODE_PREFIX}{safe_agent_name}"
        worktree_path = self.repo_path.parent / worktree_dir_name
        if not self._validate_worktree_path(worktree_path):
            raise WorktreeError(f"Worktree path {worktree_path} is outside allowed boundaries")
        return worktree_path

    def _fetch_remote(self) -> None:
        """Fetch latest changes from remote."""
        logger.info("Fetching latest changes from remote")
        self._run_git_command(["fetch", "--all", "--prune"])

    def _determine_default_branch(self) -> str:
        """Determine default branch, falling back to 'main'."""
        try:
            ref = self._run_git_command(
                ["symbolic-ref", "refs/remotes/origin/HEAD"]
            )  # default branch ref
            return ref.split("/")[-1]
        except WorktreeError:
            logger.warning("Could not determine default branch, using 'main'")
            return "main"

    def _ensure_clean_target(self, worktree_path: Path) -> None:
        """Ensure the target worktree path is clean or removed."""
        if worktree_path.exists():
            if self.dry_run:
                logger.info(f"[DRY RUN] Would remove existing worktree: {worktree_path}")
                return
            logger.warning(f"Worktree path already exists: {worktree_path}")
            try:
                self.remove_worktree(worktree_path)
            except WorktreeError as e:
                logger.error(f"Failed to remove existing worktree: {e}")
                raise WorktreeError(f"Path exists but is not a worktree: {worktree_path}") from None

    def _create_git_worktree(
        self, worktree_path: Path, branch_name: str, default_branch: str
    ) -> None:
        """Create the git worktree, handling existing branch fallback."""
        if self.dry_run:
            logger.info(
                f"[DRY RUN] Would create worktree at {worktree_path} with branch {branch_name}"
            )
            return
        logger.info(f"Creating worktree at {worktree_path} with branch {branch_name}")
        try:
            self._run_git_command(
                [
                    "worktree",
                    "add",
                    "-b",
                    branch_name,
                    str(worktree_path),
                    f"origin/{default_branch}",
                ]
            )
        except WorktreeError as e:
            if "already exists" in str(e):
                logger.info(f"Branch {branch_name} already exists, checking it out")
                self._run_git_command(["worktree", "add", str(worktree_path), branch_name])
            else:
                raise

    def create_worktree(self, branch_name: str, agent_name: str) -> Path:
        """Create a new worktree for an agent.

        Args:
            branch_name: Name of the branch to create
            agent_name: Name of the agent

        Returns:
            Path to the created worktree

        Raises:
            WorktreeError: If worktree creation fails
        """
        worktree_path = self._compute_worktree_path(agent_name)
        self._ensure_clean_target(worktree_path)
        self._fetch_remote()
        default_branch = self._determine_default_branch()
        self._create_git_worktree(worktree_path, branch_name, default_branch)
        logger.info(f"Successfully created worktree at {worktree_path}")
        return worktree_path

    def remove_worktree(self, worktree_path: Path) -> None:
        """Remove a worktree.

        Args:
            worktree_path: Path to the worktree to remove

        Raises:
            WorktreeError: If worktree removal fails
        """
        worktree_path = Path(worktree_path).resolve()

        # First, check if this is actually a worktree
        worktrees = self._list_all_worktrees()
        if str(worktree_path) not in worktrees:
            if worktree_path.exists():
                logger.warning(f"Path exists but is not a git worktree: {worktree_path}")
                # Check if it's a directory we can clean up
                if worktree_path.name.startswith(self.COCODE_PREFIX):
                    if self.dry_run:
                        logger.info(f"[DRY RUN] Would remove cocode directory: {worktree_path}")
                    else:
                        logger.info(f"Removing cocode directory: {worktree_path}")
                        shutil.rmtree(worktree_path, ignore_errors=True)
                    return
            else:
                logger.info(f"Worktree path does not exist: {worktree_path}")
                return

        if self.dry_run:
            logger.info(f"[DRY RUN] Would remove worktree at {worktree_path}")
        else:
            logger.info(f"Removing worktree at {worktree_path}")

            # Remove the worktree
            try:
                self._run_git_command(["worktree", "remove", str(worktree_path), "--force"])
                logger.info(f"Successfully removed worktree at {worktree_path}")
            except WorktreeError as e:
                # Try to prune if removal fails
                logger.warning(f"Worktree removal failed, trying prune: {e}")
                self._run_git_command(["worktree", "prune"])

                # If directory still exists, remove it manually
                if worktree_path.exists():
                    logger.info(f"Manually removing worktree directory: {worktree_path}")
                    shutil.rmtree(worktree_path, ignore_errors=True)

    def _list_all_worktrees(self) -> dict[str, str]:
        """List all worktrees (internal helper).

        Returns:
            Dictionary mapping worktree paths to their branches
        """
        output = self._run_git_command(["worktree", "list", "--porcelain"])

        worktrees = {}
        current_path = None
        current_branch = None

        for line in output.split("\n"):
            if line.startswith("worktree "):
                current_path = line[9:]  # Remove "worktree " prefix
            elif line.startswith("branch "):
                current_branch = line[7:]  # Remove "branch " prefix
                if current_path:
                    worktrees[current_path] = current_branch
                current_path = None
                current_branch = None
            elif line == "bare":
                # Skip bare repositories
                current_path = None

        return worktrees

    def list_worktrees(self) -> list[Path]:
        """List all cocode worktrees.

        Returns:
            List of paths to cocode worktrees
        """
        all_worktrees = self._list_all_worktrees()

        # Filter to only cocode worktrees
        cocode_worktrees = []
        for worktree_path in all_worktrees.keys():
            path = Path(worktree_path)
            if path.name.startswith(self.COCODE_PREFIX):
                cocode_worktrees.append(path)

        return cocode_worktrees

    def get_worktree_info(self, worktree_path: Path) -> dict:
        """Get information about a worktree.

        Args:
            worktree_path: Path to the worktree

        Returns:
            Dictionary with worktree information

        Raises:
            WorktreeError: If worktree doesn't exist
        """
        worktree_path = Path(worktree_path).resolve()
        all_worktrees = self._list_all_worktrees()

        if str(worktree_path) not in all_worktrees:
            raise WorktreeError(f"Not a git worktree: {worktree_path}")

        branch = all_worktrees[str(worktree_path)]

        # Get last commit info
        try:
            last_commit = self._run_git_command(["log", "-1", "--format=%H %s"], cwd=worktree_path)
        except WorktreeError:
            last_commit = "No commits yet"

        # Check for uncommitted changes
        try:
            status = self._run_git_command(["status", "--porcelain"], cwd=worktree_path)
            has_changes = bool(status)
        except WorktreeError:
            has_changes = False

        return {
            "path": worktree_path,
            "branch": branch,
            "last_commit": last_commit,
            "has_changes": has_changes,
        }

    def cleanup_worktrees(self) -> int:
        """Remove all cocode worktrees.

        Returns:
            Number of worktrees removed
        """
        worktrees = self.list_worktrees()
        count = 0

        for worktree_path in worktrees:
            try:
                self.remove_worktree(worktree_path)
                count += 1
            except WorktreeError as e:
                logger.error(f"Failed to remove worktree {worktree_path}: {e}")

        # Prune any stale worktree references
        try:
            self._run_git_command(["worktree", "prune"])
        except WorktreeError:
            pass

        return count

    def sync_worktree(
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

        # Validate it's a cocode worktree
        if not worktree_path.name.startswith(self.COCODE_PREFIX):
            raise WorktreeError(f"Not a cocode worktree: {worktree_path}")

        # Validate worktree exists
        all_worktrees = self._list_all_worktrees()
        if str(worktree_path) not in all_worktrees:
            raise WorktreeError(f"Worktree not found: {worktree_path}")

        return self.sync.sync(worktree_path, remote, base_branch, strategy)

    def sync_all_worktrees(
        self, remote: str = "origin", base_branch: str = "main", strategy: str = "rebase"
    ) -> dict[Path, SyncResult]:
        """Sync all cocode worktrees with upstream changes.

        Args:
            remote: Remote name to sync with
            base_branch: Base branch to sync against
            strategy: Sync strategy ('rebase' or 'merge')

        Returns:
            Dictionary mapping worktree paths to their sync results
        """
        results = {}
        worktrees = self.list_worktrees()

        for worktree_path in worktrees:
            logger.info(f"Syncing worktree: {worktree_path}")
            try:
                result = self.sync_worktree(worktree_path, remote, base_branch, strategy)
                results[worktree_path] = result
            except Exception as e:
                logger.error(f"Failed to sync {worktree_path}: {e}")
                results[worktree_path] = SyncResult(
                    status=SyncStatus.ERROR, worktree_path=worktree_path, message=str(e)
                )

        return results

    def detect_conflicts(self, worktree_path: Path) -> tuple[bool, list[str]]:
        """Detect if a worktree has merge conflicts.

        Args:
            worktree_path: Path to the worktree

        Returns:
            Tuple of (has_conflicts, list_of_conflicted_files)
        """
        return self.sync.detect_conflicts(worktree_path)
