"""Repository management for cocode."""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class RepositoryError(Exception):
    """Base exception for repository operations."""

    pass


class AuthenticationError(RepositoryError):
    """GitHub authentication error."""

    pass


class CloneError(RepositoryError):
    """Repository clone error."""

    pass


class RepositoryManager:
    """Manages repository operations including discovery and cloning."""

    def __init__(self, base_path: Path | None = None):
        """Initialize repository manager.

        Args:
            base_path: Base path to search for repositories. Defaults to current directory.
        """
        self.base_path = Path(base_path) if base_path else Path.cwd()

    def find_repositories(self, max_depth: int = 5) -> list[Path]:
        """Find all git repositories recursively.

        Searches for .git directories starting from base_path.

        Args:
            max_depth: Maximum depth to search for repositories.

        Returns:
            List of paths to repository roots (parent of .git directories).
        """
        repositories = []

        def search_dir(path: Path, current_depth: int = 0) -> None:
            """Recursively search for .git directories."""
            if current_depth > max_depth:
                return

            try:
                for item in path.iterdir():
                    if item.is_dir():
                        if item.name == ".git":
                            repositories.append(path)
                            logger.debug(f"Found repository at: {path}")
                            return
                        elif not item.name.startswith("."):
                            search_dir(item, current_depth + 1)
            except PermissionError:
                logger.debug(f"Permission denied accessing: {path}")
            except Exception as e:
                logger.debug(f"Error searching {path}: {e}")

        logger.info(f"Searching for repositories in: {self.base_path}")
        search_dir(self.base_path)
        logger.info(f"Found {len(repositories)} repositories")

        return sorted(repositories)

    def clone_repository(self, repo_url: str, target_path: Path | None = None) -> Path:
        """Clone a repository using gh CLI.

        Args:
            repo_url: GitHub repository URL or owner/repo format.
            target_path: Optional target directory for clone.

        Returns:
            Path to cloned repository.

        Raises:
            AuthenticationError: If GitHub authentication fails.
            CloneError: If repository clone fails.
        """
        if not self._check_gh_auth():
            raise AuthenticationError("GitHub CLI not authenticated. Run: gh auth login")

        if target_path is None:
            repo_name = self._extract_repo_name(repo_url)
            target_path = self.base_path / repo_name
        else:
            target_path = Path(target_path)

        if target_path.exists():
            if self._is_git_repository(target_path):
                logger.info(f"Repository already exists at: {target_path}")
                return target_path
            else:
                raise CloneError(f"Target path exists but is not a git repository: {target_path}")

        logger.info(f"Cloning {repo_url} to {target_path}")

        try:
            result = subprocess.run(
                ["gh", "repo", "clone", repo_url, str(target_path)],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                if "authentication" in result.stderr.lower():
                    raise AuthenticationError(f"Authentication failed: {result.stderr}")
                else:
                    raise CloneError(f"Clone failed: {result.stderr}")

            logger.info(f"Successfully cloned repository to: {target_path}")
            return target_path

        except FileNotFoundError as e:
            raise CloneError(
                "GitHub CLI not installed. Install from: https://cli.github.com"
            ) from e

    def _check_gh_auth(self) -> bool:
        """Check if GitHub CLI is authenticated.

        Returns:
            True if authenticated, False otherwise.

        Raises:
            CloneError: If GitHub CLI is not installed.
        """
        try:
            result = subprocess.run(
                ["gh", "auth", "status"], capture_output=True, text=True, check=False
            )
            return result.returncode == 0
        except FileNotFoundError as e:
            raise CloneError(
                "GitHub CLI not installed. Install from: https://cli.github.com"
            ) from e

    def _extract_repo_name(self, repo_url: str) -> str:
        """Extract repository name from URL or owner/repo format.

        Args:
            repo_url: Repository URL or owner/repo format.

        Returns:
            Repository name.
        """
        if "/" in repo_url:
            if repo_url.startswith("http"):
                parts = repo_url.rstrip("/").rstrip(".git").split("/")
                return parts[-1]
            else:
                return repo_url.split("/")[-1]
        return repo_url

    def _is_git_repository(self, path: Path) -> bool:
        """Check if a path is a git repository.

        Args:
            path: Path to check.

        Returns:
            True if path is a git repository, False otherwise.
        """
        git_dir = path / ".git"
        return git_dir.exists() and git_dir.is_dir()

    def get_repository_info(self, repo_path: Path) -> dict:
        """Get information about a repository.

        Args:
            repo_path: Path to repository.

        Returns:
            Dictionary with repository information.
        """
        if not self._is_git_repository(repo_path):
            raise RepositoryError(f"Not a git repository: {repo_path}")

        info = {
            "path": str(repo_path),
            "name": repo_path.name,
        }

        try:
            result = subprocess.run(
                ["git", "-C", str(repo_path), "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                info["remote_url"] = result.stdout.strip()
        except Exception as e:
            logger.debug(f"Could not get remote URL: {e}")

        try:
            result = subprocess.run(
                ["git", "-C", str(repo_path), "branch", "--show-current"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                info["current_branch"] = result.stdout.strip()
        except Exception as e:
            logger.debug(f"Could not get current branch: {e}")

        return info
