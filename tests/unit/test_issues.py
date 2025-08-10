"""Tests for GitHub issue operations."""

import json
import subprocess
from unittest.mock import Mock, patch

import pytest

from cocode.github.issues import GithubError, IssueManager


class TestIssueManager:
    """Test suite for IssueManager."""

    @patch("subprocess.run")
    def test_init_verifies_gh_cli(self, mock_run):
        """Test that initialization verifies gh CLI is installed and authenticated."""
        # Mock successful auth check
        mock_run.return_value = Mock(returncode=0)

        IssueManager()

        mock_run.assert_called_once_with(
            ["gh", "auth", "status"], capture_output=True, text=True, check=False
        )

    @patch("subprocess.run")
    def test_init_raises_if_gh_not_installed(self, mock_run):
        """Test that initialization raises error if gh CLI is not installed."""
        mock_run.side_effect = FileNotFoundError()

        with pytest.raises(GithubError, match="GitHub CLI not installed"):
            IssueManager()

    @patch("subprocess.run")
    def test_init_raises_if_not_authenticated(self, mock_run):
        """Test that initialization raises error if gh CLI is not authenticated."""
        mock_run.return_value = Mock(returncode=1)

        with pytest.raises(GithubError, match="GitHub CLI not authenticated"):
            IssueManager()

    @patch("subprocess.run")
    def test_fetch_issues_open_by_default(self, mock_run):
        """Test fetching open issues by default."""
        # Mock auth check
        auth_result = Mock(returncode=0)

        # Mock issue list result
        issues_data = [
            {
                "number": 1,
                "title": "Bug fix",
                "body": "Fix the bug",
                "state": "OPEN",
                "author": {"login": "user1"},
                "labels": [{"name": "bug"}],
                "url": "https://github.com/org/repo/issues/1",
                "createdAt": "2024-01-01T00:00:00Z",
                "updatedAt": "2024-01-02T00:00:00Z",
            }
        ]
        issues_result = Mock(returncode=0, stdout=json.dumps(issues_data))

        mock_run.side_effect = [auth_result, issues_result]

        manager = IssueManager()
        issues = manager.fetch_issues()

        # Check the gh issue list command
        assert mock_run.call_count == 2
        list_call = mock_run.call_args_list[1]
        assert list_call[0][0][:4] == ["gh", "issue", "list", "--json"]
        assert "--state" in list_call[0][0]
        assert "open" in list_call[0][0]

        # Check transformed result
        assert len(issues) == 1
        assert issues[0]["number"] == 1
        assert issues[0]["author"] == "user1"
        assert issues[0]["labels"] == ["bug"]

    @patch("subprocess.run")
    def test_fetch_issues_with_filters(self, mock_run):
        """Test fetching issues with various filters."""
        # Mock auth check
        auth_result = Mock(returncode=0)

        # Mock issue list result
        issues_result = Mock(returncode=0, stdout=json.dumps([]))

        mock_run.side_effect = [auth_result, issues_result]

        manager = IssueManager()
        manager.fetch_issues(
            state="closed", limit=10, labels=["bug", "enhancement"], assignee="user1"
        )

        # Check the command includes all filters
        list_call = mock_run.call_args_list[1]
        cmd = list_call[0][0]

        assert "--state" in cmd
        assert "closed" in cmd
        assert "--limit" in cmd
        assert "10" in cmd
        assert "--label" in cmd
        assert cmd.count("--label") == 2
        assert "bug" in cmd
        assert "enhancement" in cmd
        assert "--assignee" in cmd
        assert "user1" in cmd

    @patch("subprocess.run")
    def test_get_issue_single(self, mock_run):
        """Test fetching a single issue."""
        # Mock auth check
        auth_result = Mock(returncode=0)

        # Mock issue view result
        issue_data = {
            "number": 123,
            "title": "Feature request",
            "body": "Add new feature",
            "state": "OPEN",
            "author": {"login": "user2"},
            "labels": [{"name": "enhancement"}, {"name": "priority"}],
            "url": "https://github.com/org/repo/issues/123",
            "createdAt": "2024-01-01T00:00:00Z",
            "updatedAt": "2024-01-02T00:00:00Z",
        }
        issue_result = Mock(returncode=0, stdout=json.dumps(issue_data))

        mock_run.side_effect = [auth_result, issue_result]

        manager = IssueManager()
        issue = manager.get_issue(123)

        # Check the gh issue view command
        view_call = mock_run.call_args_list[1]
        cmd = view_call[0][0]
        assert cmd[:3] == ["gh", "issue", "view"]
        assert "123" in cmd
        assert "--json" in cmd

        # Check transformed result
        assert issue["number"] == 123
        assert issue["author"] == "user2"
        assert issue["labels"] == ["enhancement", "priority"]

    @patch("subprocess.run")
    def test_get_issue_validates_positive_number(self, mock_run):
        """Test that get_issue validates issue number is positive."""
        # Mock auth check
        auth_result = Mock(returncode=0)
        mock_run.side_effect = [auth_result]

        manager = IssueManager()

        # Test with zero
        with pytest.raises(ValueError, match="Issue number must be positive"):
            manager.get_issue(0)

        # Test with negative number
        with pytest.raises(ValueError, match="Issue number must be positive"):
            manager.get_issue(-5)

    @patch("subprocess.run")
    def test_get_issue_body(self, mock_run):
        """Test fetching issue body text."""
        # Mock auth check
        auth_result = Mock(returncode=0)

        # Mock issue view result
        issue_data = {
            "number": 456,
            "title": "Bug report",
            "body": "This is the issue body content",
            "state": "OPEN",
            "author": {"login": "user3"},
            "labels": [],
            "url": "https://github.com/org/repo/issues/456",
            "createdAt": "2024-01-01T00:00:00Z",
            "updatedAt": "2024-01-02T00:00:00Z",
        }
        issue_result = Mock(returncode=0, stdout=json.dumps(issue_data))

        mock_run.side_effect = [auth_result, issue_result]

        manager = IssueManager()
        body = manager.get_issue_body(456)

        assert body == "This is the issue body content"

    @patch("subprocess.run")
    def test_get_issue_body_validates_positive_number(self, mock_run):
        """Test that get_issue_body validates issue number is positive."""
        # Mock auth check
        auth_result = Mock(returncode=0)
        mock_run.side_effect = [auth_result]

        manager = IssueManager()

        # Test with zero
        with pytest.raises(ValueError, match="Issue number must be positive"):
            manager.get_issue_body(0)

        # Test with negative number
        with pytest.raises(ValueError, match="Issue number must be positive"):
            manager.get_issue_body(-10)

    @patch("subprocess.run")
    def test_fetch_all_issues(self, mock_run):
        """Test fetching all issues with pagination support."""
        # Mock auth check
        auth_result = Mock(returncode=0)

        # Mock issue list result
        issues_data = [
            {"number": i, "title": f"Issue {i}", "labels": [], "author": "bot"} for i in range(1, 6)
        ]
        issues_result = Mock(returncode=0, stdout=json.dumps(issues_data))

        mock_run.side_effect = [auth_result, issues_result]

        manager = IssueManager()
        all_issues = manager.fetch_all_issues()

        assert len(all_issues) == 5
        assert all_issues[0]["number"] == 1
        assert all_issues[-1]["number"] == 5

    @patch("subprocess.run")
    def test_fetch_issues_handles_errors(self, mock_run):
        """Test that fetch_issues handles gh CLI errors properly."""
        # Mock auth check
        auth_result = Mock(returncode=0)

        # Mock failed issue list
        error = subprocess.CalledProcessError(
            1, ["gh", "issue", "list"], stderr="Repository not found"
        )

        mock_run.side_effect = [auth_result, error]

        manager = IssueManager()
        with pytest.raises(GithubError, match="Failed to fetch issues"):
            manager.fetch_issues()

    @patch("subprocess.run")
    def test_fetch_issues_handles_invalid_json(self, mock_run):
        """Test that fetch_issues handles invalid JSON responses."""
        # Mock auth check
        auth_result = Mock(returncode=0)

        # Mock invalid JSON response
        invalid_result = Mock(returncode=0, stdout="not valid json")

        mock_run.side_effect = [auth_result, invalid_result]

        manager = IssueManager()
        with pytest.raises(GithubError, match="Invalid JSON from gh CLI"):
            manager.fetch_issues()
