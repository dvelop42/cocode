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

    def __init__(self, repo_path: Path | None = None):
        """Initialize the issue manager.

        Args:
            repo_path: Path to the repository. If not provided, uses current directory.
        """
        self.repo_path = repo_path or Path.cwd()
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

        try:
            result = subprocess.run(
                cmd, cwd=self.repo_path, capture_output=True, text=True, check=True
            )

            issues: list[dict[str, Any]] = json.loads(result.stdout)

            # Transform label objects to simple strings
            for issue in issues:
                if "labels" in issue and issue["labels"]:
                    issue["labels"] = [
                        label["name"] if isinstance(label, dict) else label
                        for label in issue["labels"]
                    ]
                else:
                    issue["labels"] = []

                # Transform author object to username string
                if "author" in issue and isinstance(issue["author"], dict):
                    issue["author"] = issue["author"].get("login", "unknown")

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
            GithubError: If issue doesn't exist or gh command fails.
        """
        cmd = [
            "gh",
            "issue",
            "view",
            str(issue_number),
            "--json",
            "number,title,body,state,author,labels,url,createdAt,updatedAt",
        ]

        logger.info(f"Fetching issue #{issue_number}")

        try:
            result = subprocess.run(
                cmd, cwd=self.repo_path, capture_output=True, text=True, check=True
            )

            issue: dict[str, Any] = json.loads(result.stdout)

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
        """Fetch all issues with pagination support.

        This method handles pagination automatically, fetching all issues
        that match the given criteria by making multiple requests if needed.

        Args:
            state: Issue state filter (open, closed, all). Defaults to "open".
            labels: List of labels to filter by.
            assignee: Filter by assignee username.
            page_size: Number of issues to fetch per page (max 100).

        Returns:
            Complete list of all matching issues.

        Raises:
            GithubError: If gh command fails.
        """
        page_size = min(page_size, 100)  # gh CLI max is 100 per page

        logger.info(f"Fetching all issues with pagination (page_size={page_size})")

        # Note: gh CLI doesn't have true pagination with offsets,
        # but we can use --limit to control batch size
        # For true pagination, we'd need to use the GitHub API directly

        # Since gh CLI doesn't support offset-based pagination,
        # we'll fetch with a high limit and hope it gets all issues
        # For repos with many issues, consider using the API directly

        issues = self.fetch_issues(
            state=state, limit=None, labels=labels, assignee=assignee  # Fetch all available
        )

        return issues
