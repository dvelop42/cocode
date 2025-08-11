"""Custom header component for Cocode TUI."""

import json
import logging
import re
import subprocess
from urllib.parse import urlparse

from textual import work
from textual.reactive import reactive
from textual.widgets import Static

logger = logging.getLogger(__name__)


class CocodeHeader(Static):
    """Custom header displaying repository info, issue details, and auth status."""

    # Constants
    MAX_TITLE_LENGTH = 40
    REPO_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9._-]+$")
    GITHUB_REPO_PATTERN = re.compile(r"^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$")

    # Reactive attributes
    repo_name = reactive("")
    repo_owner = reactive("")
    default_branch = reactive("main")
    issue_number = reactive(0)
    issue_title = reactive("")
    auth_status = reactive(False)

    def __init__(
        self,
        issue_number: int = 0,
        issue_title: str = "",
        dry_run: bool = False,
        **kwargs: object,
    ) -> None:
        """Initialize the header.

        Args:
            issue_number: GitHub issue number
            issue_title: Issue title
            dry_run: Whether in dry run mode
            **kwargs: Additional arguments for Static
        """
        super().__init__(**kwargs)
        self.issue_number = issue_number
        self.issue_title = issue_title
        self.dry_run = dry_run

    def on_mount(self) -> None:
        """Set up styling and fetch data when mounted."""
        self.styles.background = "#004578"  # Primary blue color
        self.styles.color = "#ffffff"
        self.styles.padding = (0, 1)
        self.styles.height = 1
        self.styles.dock = "top"

        # Start async data fetching
        self.fetch_header_data()

    @work(thread=True)
    def fetch_header_data(self) -> None:
        """Fetch all header data in a background thread."""
        self._fetch_repo_info()
        self._check_auth_status()
        self._fetch_issue_title()

    def _validate_repo_name(self, name: str) -> bool:
        """Validate repository name for security.

        Args:
            name: Repository name to validate

        Returns:
            True if valid, False otherwise
        """
        return bool(self.REPO_NAME_PATTERN.match(name))

    def _validate_repo_path(self, path: str) -> bool:
        """Validate full repository path (owner/repo).

        Args:
            path: Repository path to validate

        Returns:
            True if valid, False otherwise
        """
        return bool(self.GITHUB_REPO_PATTERN.match(path))

    def _parse_github_url(self, url: str) -> tuple[str, str]:
        """Parse GitHub URL to extract owner and repo.

        Args:
            url: GitHub remote URL

        Returns:
            Tuple of (owner, repo) or ("", "") if parsing fails
        """
        try:
            # Remove .git suffix if present
            url = url.removesuffix(".git")

            if url.startswith("git@github.com:"):
                # SSH format: git@github.com:owner/repo
                path = url.replace("git@github.com:", "")
            elif "github.com" in url:
                # HTTPS format: https://github.com/owner/repo
                parsed = urlparse(url)
                path = parsed.path.lstrip("/")
            else:
                return "", ""

            # Split owner/repo
            if "/" in path:
                owner, repo = path.split("/", 1)
                # Validate for security
                if self._validate_repo_name(owner) and self._validate_repo_name(repo):
                    return owner, repo

        except (ValueError, AttributeError) as e:
            logger.debug(f"Failed to parse GitHub URL '{url}': {e}")

        return "", ""

    def _fetch_repo_info(self) -> None:
        """Fetch repository information from git."""
        # Get remote URL
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            if result.returncode == 0:
                remote_url = result.stdout.strip()
                owner, repo = self._parse_github_url(remote_url)
                if owner and repo:
                    self.repo_owner = owner
                    self.repo_name = repo
                elif repo:
                    self.repo_name = repo
        except subprocess.TimeoutExpired:
            logger.debug("Timeout fetching git remote URL")
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            logger.debug(f"Failed to fetch git remote: {e}")

        # Get default branch
        try:
            result = subprocess.run(
                ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            if result.returncode == 0:
                # Format: refs/remotes/origin/main
                branch = result.stdout.strip().split("/")[-1]
                if branch and self._validate_repo_name(branch):
                    self.default_branch = branch
            else:
                # Fallback: try to get current branch
                result = subprocess.run(
                    ["git", "branch", "--show-current"],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=5,
                )
                if result.returncode == 0:
                    branch = result.stdout.strip()
                    if branch and self._validate_repo_name(branch):
                        self.default_branch = branch
        except subprocess.TimeoutExpired:
            logger.debug("Timeout fetching git branch")
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            logger.debug(f"Failed to fetch git branch: {e}")

    def _check_auth_status(self) -> None:
        """Check GitHub CLI authentication status."""
        try:
            result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            self.auth_status = result.returncode == 0
        except subprocess.TimeoutExpired:
            logger.debug("Timeout checking gh auth status")
            self.auth_status = False
        except FileNotFoundError:
            logger.debug("gh CLI not installed")
            self.auth_status = False
        except subprocess.SubprocessError as e:
            logger.debug(f"Failed to check gh auth: {e}")
            self.auth_status = False

    def _fetch_issue_title(self) -> None:
        """Fetch issue title from GitHub if not provided."""
        if not self.issue_number or self.issue_title:
            return

        if not self.repo_owner or not self.repo_name:
            return

        # Validate repo path for security
        repo_path = f"{self.repo_owner}/{self.repo_name}"
        if not self._validate_repo_path(repo_path):
            logger.warning(f"Invalid repository path: {repo_path}")
            return

        try:
            result = subprocess.run(
                [
                    "gh",
                    "issue",
                    "view",
                    str(self.issue_number),
                    "--repo",
                    repo_path,
                    "--json",
                    "title",
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,  # Allow more time for network operation
            )
            if result.returncode == 0 and result.stdout:
                try:
                    data = json.loads(result.stdout)
                    title = data.get("title", "")
                    if title:
                        self.issue_title = title
                except json.JSONDecodeError as e:
                    logger.debug(f"Failed to parse issue JSON: {e}")
        except subprocess.TimeoutExpired:
            logger.debug("Timeout fetching issue title from GitHub")
        except FileNotFoundError:
            logger.debug("gh CLI not installed")
        except subprocess.SubprocessError as e:
            logger.debug(f"Failed to fetch issue title: {e}")

    def render(self) -> str:
        """Render the header content."""
        parts = []

        # Repository info
        if self.repo_owner and self.repo_name:
            parts.append(f"📦 {self.repo_owner}/{self.repo_name}")
        elif self.repo_name:
            parts.append(f"📦 {self.repo_name}")
        else:
            parts.append("📦 cocode")

        # Default branch
        parts.append(f"🌿 {self.default_branch}")

        # Issue info
        if self.issue_number:
            if self.issue_title:
                # Truncate title if too long
                title = self.issue_title[: self.MAX_TITLE_LENGTH]
                if len(self.issue_title) > self.MAX_TITLE_LENGTH:
                    title += "..."
                parts.append(f"🎯 #{self.issue_number}: {title}")
            else:
                parts.append(f"🎯 Issue #{self.issue_number}")

        # Auth status
        if self.auth_status:
            parts.append("🔐 ✓")
        else:
            parts.append("🔐 ✗")

        # Dry run indicator
        if self.dry_run:
            parts.append("🔍 DRY RUN")

        return " │ ".join(parts)
