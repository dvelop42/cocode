"""Git worktree management."""

from pathlib import Path


class WorktreeManager:
    """Manages git worktrees for agents."""

    def __init__(self, repo_path: Path):
        """Initialize worktree manager."""
        self.repo_path = repo_path

    def create_worktree(self, branch_name: str, agent_name: str) -> Path:
        """Create a new worktree for an agent."""
        raise NotImplementedError("Worktree creation not yet implemented")

    def remove_worktree(self, worktree_path: Path) -> None:
        """Remove a worktree."""
        raise NotImplementedError("Worktree removal not yet implemented")

    def list_worktrees(self) -> list[Path]:
        """List all cocode worktrees."""
        raise NotImplementedError("Worktree listing not yet implemented")
