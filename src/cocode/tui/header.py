"""Custom header component for Cocode TUI."""

import subprocess

from textual.reactive import reactive
from textual.widgets import Static


class CocodeHeader(Static):
    """Custom header displaying repository info, issue details, and auth status."""

    repo_name = reactive("", layout=True)
    repo_owner = reactive("", layout=True)
    default_branch = reactive("main", layout=True)
    issue_number = reactive(0, layout=True)
    issue_title = reactive("", layout=True)
    auth_status = reactive(False, layout=True)

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
        self._fetch_repo_info()
        self._check_auth_status()
        self._fetch_issue_title()

    def _fetch_repo_info(self) -> None:
        """Fetch repository information from git."""
        try:
            # Get remote URL and parse repo info
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                remote_url = result.stdout.strip()
                # Parse GitHub URL formats
                if "github.com" in remote_url:
                    # Handle both SSH and HTTPS formats
                    if remote_url.startswith("git@"):
                        # SSH format: git@github.com:owner/repo.git
                        parts = remote_url.split(":")[-1]
                    else:
                        # HTTPS format: https://github.com/owner/repo.git
                        url_parts = remote_url.split("/")[-2:]
                        parts = "/".join(url_parts)

                    # Remove .git suffix if present
                    parts = parts.removesuffix(".git")

                    # Extract owner and repo
                    if "/" in parts:
                        owner, repo = parts.split("/", 1)
                        self.repo_owner = owner
                        self.repo_name = repo
                    else:
                        self.repo_name = parts

            # Get default branch
            result = subprocess.run(
                ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                # Format: refs/remotes/origin/main
                self.default_branch = result.stdout.strip().split("/")[-1]
            else:
                # Fallback: try to get current branch
                result = subprocess.run(
                    ["git", "branch", "--show-current"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode == 0 and result.stdout.strip():
                    self.default_branch = result.stdout.strip()

        except Exception:
            # Silently handle errors - use defaults
            pass

    def _check_auth_status(self) -> None:
        """Check GitHub CLI authentication status."""
        try:
            result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.auth_status = result.returncode == 0
        except FileNotFoundError:
            # gh CLI not installed
            self.auth_status = False
        except Exception:
            self.auth_status = False

    def _fetch_issue_title(self) -> None:
        """Fetch issue title from GitHub if not provided."""
        if self.issue_number and not self.issue_title and self.repo_owner and self.repo_name:
            try:
                result = subprocess.run(
                    [
                        "gh",
                        "issue",
                        "view",
                        str(self.issue_number),
                        "--repo",
                        f"{self.repo_owner}/{self.repo_name}",
                        "--json",
                        "title",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode == 0:
                    import json

                    data = json.loads(result.stdout)
                    self.issue_title = data.get("title", "")
            except Exception:
                # Silently handle errors
                pass

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
                max_title_len = 40
                title = self.issue_title[:max_title_len]
                if len(self.issue_title) > max_title_len:
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

    def on_mount(self) -> None:
        """Set up styling when mounted."""
        self.styles.background = "#004578"  # Primary blue color
        self.styles.color = "#ffffff"
        self.styles.padding = (0, 1)
        self.styles.height = 1
        self.styles.dock = "top"
