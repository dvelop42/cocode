"""Input validation utilities for cocode."""

import re
from pathlib import Path


def validate_issue_number(issue: int) -> bool:
    """Validate GitHub issue number.

    Args:
        issue: Issue number to validate

    Returns:
        True if valid, False otherwise
    """
    return isinstance(issue, int) and not isinstance(issue, bool) and issue > 0


def sanitize_branch_name(name: str) -> str:
    """Sanitize a string to be a valid git branch name.

    Args:
        name: Raw branch name

    Returns:
        Sanitized branch name
    """
    # Replace invalid characters with hyphens
    sanitized = re.sub(r"[^a-zA-Z0-9/_-]", "-", name)
    # Remove leading/trailing hyphens
    sanitized = sanitized.strip("-/")
    # Collapse multiple hyphens
    sanitized = re.sub(r"-+", "-", sanitized)
    # Ensure it doesn't start with a dot
    if sanitized.startswith("."):
        sanitized = sanitized[1:]
    return sanitized or "branch"


def validate_agent_path(path: Path, worktree_root: Path) -> bool:
    """Ensure agent cannot escape worktree boundaries.

    Args:
        path: Path to validate
        worktree_root: Root of the worktree

    Returns:
        True if path is within worktree, False otherwise
    """
    try:
        resolved_path = path.resolve()
        resolved_root = worktree_root.resolve()
        # Python 3.9+ has is_relative_to, for compatibility we use this approach
        try:
            resolved_path.relative_to(resolved_root)
            return True
        except ValueError:
            return False
    except (ValueError, RuntimeError):
        return False


def validate_repo_path(path: Path | None = None) -> bool:
    """Validate that path is a git repository.

    Args:
        path: Path to check (defaults to current directory)

    Returns:
        True if valid git repo, False otherwise
    """
    repo_path = path or Path.cwd()
    git_dir = repo_path / ".git"
    return git_dir.exists() and (git_dir.is_dir() or git_dir.is_file())
