"""Tests for the custom header component."""

import json
import subprocess
from unittest.mock import Mock, patch

from cocode.tui.header import CocodeHeader


class TestCocodeHeader:
    """Test suite for CocodeHeader component."""

    def test_header_initialization(self):
        """Test header initializes with correct values."""
        header = CocodeHeader(
            issue_number=123,
            issue_title="Test Issue",
            dry_run=True,
        )
        assert header.issue_number == 123
        assert header.issue_title == "Test Issue"
        assert header.dry_run is True

    def test_repo_name_validation(self):
        """Test repository name validation."""
        header = CocodeHeader()

        # Valid names
        assert header._validate_repo_name("valid-repo")
        assert header._validate_repo_name("repo_name")
        assert header._validate_repo_name("repo.name")
        assert header._validate_repo_name("123repo")

        # Invalid names
        assert not header._validate_repo_name("repo/name")
        assert not header._validate_repo_name("repo name")
        assert not header._validate_repo_name("repo@name")
        assert not header._validate_repo_name("../../etc/passwd")

    def test_repo_path_validation(self):
        """Test full repository path validation."""
        header = CocodeHeader()

        # Valid paths
        assert header._validate_repo_path("owner/repo")
        assert header._validate_repo_path("my-org/my-repo")
        assert header._validate_repo_path("user123/repo.name")

        # Invalid paths
        assert not header._validate_repo_path("invalid")
        assert not header._validate_repo_path("owner/repo/extra")
        assert not header._validate_repo_path("owner@host/repo")
        assert not header._validate_repo_path("../../../etc/passwd")

    def test_parse_github_url_ssh(self):
        """Test parsing SSH GitHub URLs."""
        header = CocodeHeader()

        # Standard SSH format
        owner, repo = header._parse_github_url("git@github.com:owner/repo.git")
        assert owner == "owner"
        assert repo == "repo"

        # Without .git suffix
        owner, repo = header._parse_github_url("git@github.com:my-org/my-repo")
        assert owner == "my-org"
        assert repo == "my-repo"

    def test_parse_github_url_https(self):
        """Test parsing HTTPS GitHub URLs."""
        header = CocodeHeader()

        # Standard HTTPS format
        owner, repo = header._parse_github_url("https://github.com/owner/repo.git")
        assert owner == "owner"
        assert repo == "repo"

        # Without .git suffix
        owner, repo = header._parse_github_url("https://github.com/my-org/my-repo")
        assert owner == "my-org"
        assert repo == "my-repo"

    def test_parse_github_url_invalid(self):
        """Test parsing invalid URLs returns empty strings."""
        header = CocodeHeader()

        # Non-GitHub URLs
        owner, repo = header._parse_github_url("https://gitlab.com/owner/repo")
        assert owner == ""
        assert repo == ""

        # Malformed URLs
        owner, repo = header._parse_github_url("not-a-url")
        assert owner == ""
        assert repo == ""

        # Dangerous paths
        owner, repo = header._parse_github_url("git@github.com:../../etc/passwd")
        assert owner == ""
        assert repo == ""

    @patch("cocode.tui.header.subprocess.run")
    def test_fetch_repo_info_success(self, mock_run):
        """Test successful fetching of repository info."""
        header = CocodeHeader()

        # Mock git remote response
        mock_run.side_effect = [
            Mock(
                returncode=0,
                stdout="git@github.com:dvelop42/cocode.git",
            ),
            Mock(
                returncode=0,
                stdout="refs/remotes/origin/main",
            ),
        ]

        header._fetch_repo_info()

        # Verify subprocess was called with correct arguments
        assert mock_run.call_count == 2
        assert mock_run.call_args_list[0][0][0] == ["git", "remote", "get-url", "origin"]
        assert mock_run.call_args_list[1][0][0] == [
            "git",
            "symbolic-ref",
            "refs/remotes/origin/HEAD",
        ]

    @patch("cocode.tui.header.subprocess.run")
    def test_fetch_repo_info_fallback_branch(self, mock_run):
        """Test fallback to current branch when origin/HEAD fails."""
        header = CocodeHeader()

        # Mock git remote and branch responses
        mock_run.side_effect = [
            Mock(returncode=0, stdout="git@github.com:owner/repo.git"),
            Mock(returncode=1),  # origin/HEAD fails
            Mock(returncode=0, stdout="feature-branch"),  # current branch succeeds
        ]

        header._fetch_repo_info()

        assert header._reactive_default_branch == "feature-branch"

    @patch("cocode.tui.header.subprocess.run")
    def test_fetch_repo_info_timeout(self, mock_run):
        """Test handling of subprocess timeout."""
        header = CocodeHeader()

        mock_run.side_effect = subprocess.TimeoutExpired("git", 5)

        # Should not raise, just log
        header._fetch_repo_info()

        # Verify subprocess was called (first call times out, preventing second)
        assert mock_run.call_count >= 1

    @patch("cocode.tui.header.subprocess.run")
    def test_check_auth_status_authenticated(self, mock_run):
        """Test checking GitHub CLI auth status when authenticated."""
        header = CocodeHeader()

        mock_run.return_value = Mock(returncode=0)

        header._check_auth_status()

        assert header._reactive_auth_status is True

    @patch("cocode.tui.header.subprocess.run")
    def test_check_auth_status_not_authenticated(self, mock_run):
        """Test checking GitHub CLI auth status when not authenticated."""
        header = CocodeHeader()

        mock_run.return_value = Mock(returncode=1)

        header._check_auth_status()

        assert header._reactive_auth_status is False

    @patch("cocode.tui.header.subprocess.run")
    def test_check_auth_status_gh_not_installed(self, mock_run):
        """Test handling when gh CLI is not installed."""
        header = CocodeHeader()

        mock_run.side_effect = FileNotFoundError()

        header._check_auth_status()

        assert header._reactive_auth_status is False

    @patch("cocode.tui.header.subprocess.run")
    def test_fetch_issue_title_success(self, mock_run):
        """Test successful fetching of issue title."""
        header = CocodeHeader(issue_number=123)
        header._reactive_repo_owner = "owner"
        header._reactive_repo_name = "repo"

        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({"title": "Test Issue Title"}),
        )

        header._fetch_issue_title()

        assert header._reactive_issue_title == "Test Issue Title"

    @patch("cocode.tui.header.subprocess.run")
    def test_fetch_issue_title_invalid_json(self, mock_run):
        """Test handling of invalid JSON response."""
        header = CocodeHeader(issue_number=123)
        header._reactive_repo_owner = "owner"
        header._reactive_repo_name = "repo"

        mock_run.return_value = Mock(
            returncode=0,
            stdout="not valid json",
        )

        header._fetch_issue_title()

        assert header._reactive_issue_title == ""

    @patch("cocode.tui.header.subprocess.run")
    def test_fetch_issue_title_skip_if_provided(self, mock_run):
        """Test that issue title is not fetched if already provided."""
        header = CocodeHeader(
            issue_number=123,
            issue_title="Already Set",
        )
        header._reactive_repo_owner = "owner"
        header._reactive_repo_name = "repo"

        header._fetch_issue_title()

        # Should not call subprocess
        mock_run.assert_not_called()
        assert header._reactive_issue_title == "Already Set"

    def test_fetch_issue_title_skip_invalid_repo(self):
        """Test that issue title fetch is skipped for invalid repo paths."""
        header = CocodeHeader(issue_number=123)
        header._reactive_repo_owner = "../../etc"
        header._reactive_repo_name = "passwd"

        with patch("cocode.tui.header.subprocess.run") as mock_run:
            header._fetch_issue_title()
            # Should not call subprocess due to validation
            mock_run.assert_not_called()

    def test_render_full_info(self):
        """Test rendering with all information available."""
        header = CocodeHeader(
            issue_number=123,
            issue_title="Test Issue",
            dry_run=True,
        )
        # Use private attributes to bypass reactive
        header._reactive_repo_owner = "owner"
        header._reactive_repo_name = "repo"
        header._reactive_default_branch = "main"
        header._reactive_auth_status = True

        output = header.render()

        assert "📦 owner/repo" in output
        assert "🌿 main" in output
        assert "🎯 #123: Test Issue" in output
        assert "🔐 ✓" in output
        assert "🔍 DRY RUN" in output

    def test_render_partial_info(self):
        """Test rendering with partial information."""
        header = CocodeHeader()
        header._reactive_repo_name = "repo"
        header._reactive_auth_status = False

        output = header.render()

        assert "📦 repo" in output
        assert "🌿 main" in output  # default
        assert "🔐 ✗" in output
        assert "🔍 DRY RUN" not in output

    def test_render_truncate_long_title(self):
        """Test that long issue titles are truncated."""
        long_title = "A" * 100
        header = CocodeHeader(
            issue_number=123,
            issue_title=long_title,
        )

        output = header.render()

        # Should be truncated to MAX_TITLE_LENGTH + "..."
        assert f"🎯 #123: {'A' * header.MAX_TITLE_LENGTH}..." in output

    def test_render_no_repo_info(self):
        """Test rendering when no repository info is available."""
        header = CocodeHeader()
        # Ensure empty strings for repo info
        header._reactive_repo_owner = ""
        header._reactive_repo_name = ""

        output = header.render()

        assert "📦 cocode" in output  # fallback

    @patch("cocode.tui.header.subprocess.run")
    def test_fetch_header_data_integration(self, mock_run):
        """Test the full fetch_header_data workflow."""
        header = CocodeHeader(issue_number=123)

        # Mock all subprocess calls
        mock_run.side_effect = [
            # _fetch_repo_info calls
            Mock(returncode=0, stdout="git@github.com:owner/repo.git"),
            Mock(returncode=0, stdout="refs/remotes/origin/develop"),
            # _check_auth_status call
            Mock(returncode=0),
            # _fetch_issue_title call - won't be called without repo info set
        ]

        # Run the methods that would be called by the worker
        header._fetch_repo_info()
        header._check_auth_status()

        # Manually set repo info for issue title fetch test
        header._reactive_repo_owner = "owner"
        header._reactive_repo_name = "repo"

        # Add the issue title response to the mock
        mock_run.side_effect = [Mock(returncode=0, stdout=json.dumps({"title": "Issue Title"}))]
        header._fetch_issue_title()

        # Verify all methods were called
        assert mock_run.call_count == 4
