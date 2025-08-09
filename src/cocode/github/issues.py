"""GitHub issue operations via gh CLI."""


class IssueManager:
    """Manages GitHub issues via gh CLI."""

    def get_issue(self, issue_number: int) -> dict:
        """Get issue details."""
        raise NotImplementedError("Issue fetching not yet implemented")

    def get_issue_body(self, issue_number: int) -> str:
        """Get issue body text."""
        raise NotImplementedError("Issue body fetching not yet implemented")
