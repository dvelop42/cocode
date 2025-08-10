"""GitHub issue operations via gh CLI."""

import json
import logging
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class GithubError(Exception):
    """Base exception for GitHub operations."""

    pass


class IssueManager:
    """Manages GitHub issues via gh CLI."""

    def __init__(self, repo_path: Path | None = None, dry_run: bool = False):
        """Initialize the issue manager.

        Args:
            repo_path: Path to the repository. If not provided, uses current directory.
            dry_run: If True, preview operations without executing them.
        """
        self.repo_path = repo_path or Path.cwd()
        self.dry_run = dry_run
        if not self.dry_run:
            self._verify_gh_cli()

    def _verify_gh_cli(self) -> None:
        """Verify gh CLI is installed and authenticated."""
        try:
            result = subprocess.run(
                ["gh", "auth", "status"], capture_output=True, text=True, check=False
            )
            if result.returncode != 0:
                raise GithubError("GitHub CLI not authenticated. Run: gh auth login")
        except FileNotFoundError as e:
            raise GithubError(
                "GitHub CLI not installed. Install from: https://cli.github.com"
            ) from e

    def _transform_issue(self, issue: dict[str, Any]) -> dict[str, Any]:
        """Transform raw issue data from gh CLI.

        Args:
            issue: Raw issue dictionary from gh CLI.

        Returns:
            Transformed issue with normalized labels and author.
        """
        # Transform label objects to simple strings
        if "labels" in issue and issue["labels"]:
            issue["labels"] = [
                label["name"] if isinstance(label, dict) else label for label in issue["labels"]
            ]
        else:
            issue["labels"] = []

        # Transform author object to username string
        if "author" in issue and isinstance(issue["author"], dict):
            issue["author"] = issue["author"].get("login", "unknown")

        return issue

    def fetch_issues(
        self,
        state: str = "open",
        limit: int | None = None,
        labels: list[str] | None = None,
        assignee: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch issues from the repository.

        Args:
            state: Issue state filter (open, closed, all). Defaults to "open".
            limit: Maximum number of issues to fetch. None for all issues.
            labels: List of labels to filter by.
            assignee: Filter by assignee username.

        Returns:
            List of issue dictionaries with keys:
                - number: Issue number
                - title: Issue title
                - body: Issue body content
                - state: Issue state (OPEN, CLOSED)
                - author: Issue author username
                - labels: List of label names
                - url: Issue URL
                - created_at: Creation timestamp
                - updated_at: Last update timestamp

        Raises:
            GithubError: If gh command fails.
        """
        cmd = [
            "gh",
            "issue",
            "list",
            "--json",
            "number,title,body,state,author,labels,url,createdAt,updatedAt",
            "--state",
            state,
        ]

        # Add optional filters
        if limit:
            cmd.extend(["--limit", str(limit)])

        if labels:
            for label in labels:
                cmd.extend(["--label", label])

        if assignee:
            cmd.extend(["--assignee", assignee])

        logger.info(f"Fetching issues with state={state}, limit={limit}")
        logger.debug(f"Running command: {' '.join(cmd)}")

        if self.dry_run:
            logger.info(f"[DRY RUN] Would execute: {' '.join(cmd)}")
            # Return sample data in dry run mode
            return [
                {
                    "number": 1,
                    "title": "[DRY RUN] Sample Issue",
                    "body": "This is a sample issue in dry run mode",
                    "state": "OPEN",
                    "author": "sample-user",
                    "labels": ["dry-run"],
                    "url": "https://github.com/example/repo/issues/1",
                    "createdAt": "2024-01-01T00:00:00Z",
                    "updatedAt": "2024-01-01T00:00:00Z",
                }
            ]

        try:
            result = subprocess.run(
                cmd, cwd=self.repo_path, capture_output=True, text=True, check=True
            )

            issues: list[dict[str, Any]] = json.loads(result.stdout)

            # Transform each issue
            issues = [self._transform_issue(issue) for issue in issues]

            logger.info(f"Fetched {len(issues)} issues")
            return issues

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            logger.error(f"Failed to fetch issues: {error_msg}")
            raise GithubError(f"Failed to fetch issues: {error_msg}") from e
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse gh output: {e}")
            raise GithubError(f"Invalid JSON from gh CLI: {e}") from e

    def get_issue(self, issue_number: int) -> dict[str, Any]:
        """Get issue details.

        Args:
            issue_number: The issue number to fetch.

        Returns:
            Issue dictionary with same keys as fetch_issues().

        Raises:
            ValueError: If issue_number is not positive.
            GithubError: If issue doesn't exist or gh command fails.
        """
        if issue_number <= 0:
            raise ValueError("Issue number must be positive")
        cmd = [
            "gh",
            "issue",
            "view",
            str(issue_number),
            "--json",
            "number,title,body,state,author,labels,url,createdAt,updatedAt",
        ]

        logger.info(f"Fetching issue #{issue_number}")

        if self.dry_run:
            logger.info(f"[DRY RUN] Would execute: {' '.join(cmd)}")
            # Return sample data in dry run mode
            return {
                "number": issue_number,
                "title": f"[DRY RUN] Sample Issue #{issue_number}",
                "body": f"This is a sample issue #{issue_number} in dry run mode",
                "state": "OPEN",
                "author": "sample-user",
                "labels": ["dry-run"],
                "url": f"https://github.com/example/repo/issues/{issue_number}",
                "createdAt": "2024-01-01T00:00:00Z",
                "updatedAt": "2024-01-01T00:00:00Z",
            }

        try:
            result = subprocess.run(
                cmd, cwd=self.repo_path, capture_output=True, text=True, check=True
            )

            issue: dict[str, Any] = json.loads(result.stdout)

            # Transform the issue
            issue = self._transform_issue(issue)

            logger.info(f"Successfully fetched issue #{issue_number}")
            return issue

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            logger.error(f"Failed to fetch issue #{issue_number}: {error_msg}")
            raise GithubError(f"Failed to fetch issue #{issue_number}: {error_msg}") from e
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse gh output: {e}")
            raise GithubError(f"Invalid JSON from gh CLI: {e}") from e

    def get_issue_body(self, issue_number: int) -> str:
        """Get issue body text.

        Args:
            issue_number: The issue number to fetch.

        Returns:
            The issue body content as a string.

        Raises:
            ValueError: If issue_number is not positive.
            GithubError: If issue doesn't exist or gh command fails.
        """
        issue = self.get_issue(issue_number)
        body: str = issue.get("body", "")
        return body

    def fetch_all_issues(
        self,
        state: str = "open",
        labels: list[str] | None = None,
        assignee: str | None = None,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        """Fetch all available issues (limited by gh CLI capabilities).

        Note: The gh CLI doesn't support true offset-based pagination.
        This method fetches all issues that gh CLI returns (typically up to 1000).
        For repositories with more issues, consider using the GitHub API directly.

        Args:
            state: Issue state filter (open, closed, all). Defaults to "open".
            labels: List of labels to filter by.
            assignee: Filter by assignee username.
            page_size: Ignored - kept for API compatibility. gh CLI doesn't support
                      true pagination.

        Returns:
            Complete list of all matching issues that gh CLI can return.

        Raises:
            GithubError: If gh command fails.
        """
        logger.info(
            f"Fetching all available issues (state={state}). " "Note: gh CLI pagination is limited."
        )

        # gh CLI doesn't support offset-based pagination, so we fetch all available
        # issues in a single request. The CLI typically limits to ~1000 issues.
        issues = self.fetch_issues(state=state, limit=None, labels=labels, assignee=assignee)

        return issues
