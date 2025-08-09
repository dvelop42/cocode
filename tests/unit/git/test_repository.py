"""Tests for repository manager."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from cocode.git.repository import (
    AuthenticationError,
    CloneError,
    RepositoryError,
    RepositoryManager,
)


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for testing."""
    return tmp_path


@pytest.fixture
def repo_manager(temp_dir):
    """Create a RepositoryManager instance."""
    return RepositoryManager(base_path=temp_dir)


class TestRepositoryManager:
    """Test RepositoryManager class."""

    def test_init_default_path(self):
        """Test initialization with default path."""
        with patch("cocode.git.repository.Path.cwd") as mock_cwd:
            mock_cwd.return_value = Path("/current/dir")
            manager = RepositoryManager()
            assert manager.base_path == Path("/current/dir")

    def test_init_custom_path(self, temp_dir):
        """Test initialization with custom path."""
        manager = RepositoryManager(base_path=temp_dir)
        assert manager.base_path == temp_dir

    def test_find_repositories_empty(self, repo_manager, temp_dir):
        """Test finding repositories in empty directory."""
        repos = repo_manager.find_repositories()
        assert repos == []

    def test_find_repositories_single(self, repo_manager, temp_dir):
        """Test finding single repository."""
        repo_dir = temp_dir / "my-repo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()

        repos = repo_manager.find_repositories()
        assert len(repos) == 1
        assert repos[0] == repo_dir

    def test_find_repositories_multiple(self, repo_manager, temp_dir):
        """Test finding multiple repositories."""
        repo1 = temp_dir / "repo1"
        repo1.mkdir()
        (repo1 / ".git").mkdir()

        repo2 = temp_dir / "nested" / "repo2"
        repo2.mkdir(parents=True)
        (repo2 / ".git").mkdir()

        repos = repo_manager.find_repositories()
        assert len(repos) == 2
        assert repo1 in repos
        assert repo2 in repos

    def test_find_repositories_max_depth(self, repo_manager, temp_dir):
        """Test max depth limit for finding repositories."""
        deep_repo = temp_dir / "a" / "b" / "c" / "d" / "e" / "f" / "repo"
        deep_repo.mkdir(parents=True)
        (deep_repo / ".git").mkdir()

        repos = repo_manager.find_repositories(max_depth=3)
        assert len(repos) == 0

        repos = repo_manager.find_repositories(max_depth=10)
        assert len(repos) == 1
        assert repos[0] == deep_repo

    def test_find_repositories_ignores_hidden(self, repo_manager, temp_dir):
        """Test that hidden directories (except .git) are ignored."""
        visible_repo = temp_dir / "visible"
        visible_repo.mkdir()
        (visible_repo / ".git").mkdir()

        hidden_dir = temp_dir / ".hidden"
        hidden_dir.mkdir()
        hidden_repo = hidden_dir / "repo"
        hidden_repo.mkdir()
        (hidden_repo / ".git").mkdir()

        repos = repo_manager.find_repositories()
        assert len(repos) == 1
        assert repos[0] == visible_repo

    @patch("subprocess.run")
    def test_clone_repository_success(self, mock_run, repo_manager, temp_dir):
        """Test successful repository clone."""
        mock_run.side_effect = [
            Mock(returncode=0),
            Mock(returncode=0, stdout="", stderr=""),
        ]

        repo_url = "owner/repo"
        result = repo_manager.clone_repository(repo_url)

        expected_path = temp_dir / "repo"
        assert result == expected_path

        mock_run.assert_any_call(
            ["gh", "auth", "status"], capture_output=True, text=True, check=False
        )
        mock_run.assert_any_call(
            ["gh", "repo", "clone", repo_url, str(expected_path)],
            capture_output=True,
            text=True,
            check=False,
        )

    @patch("subprocess.run")
    def test_clone_repository_custom_path(self, mock_run, repo_manager, temp_dir):
        """Test cloning to custom path."""
        mock_run.side_effect = [
            Mock(returncode=0),
            Mock(returncode=0),
        ]

        custom_path = temp_dir / "custom" / "location"
        result = repo_manager.clone_repository("owner/repo", custom_path)

        assert result == custom_path
        mock_run.assert_any_call(
            ["gh", "repo", "clone", "owner/repo", str(custom_path)],
            capture_output=True,
            text=True,
            check=False,
        )

    @patch("subprocess.run")
    def test_clone_repository_auth_failure(self, mock_run, repo_manager):
        """Test authentication failure."""
        mock_run.return_value = Mock(returncode=1)

        with pytest.raises(AuthenticationError) as exc_info:
            repo_manager.clone_repository("owner/repo")

        assert "not authenticated" in str(exc_info.value)

    @patch("subprocess.run")
    def test_clone_repository_clone_error(self, mock_run, repo_manager):
        """Test clone failure."""
        mock_run.side_effect = [
            Mock(returncode=0),
            Mock(returncode=1, stderr="repository not found"),
        ]

        with pytest.raises(CloneError) as exc_info:
            repo_manager.clone_repository("owner/repo")

        assert "repository not found" in str(exc_info.value)

    @patch("subprocess.run")
    def test_clone_repository_auth_error_in_clone(self, mock_run, repo_manager):
        """Test authentication error during clone."""
        mock_run.side_effect = [
            Mock(returncode=0),
            Mock(returncode=1, stderr="Authentication failed"),
        ]

        with pytest.raises(AuthenticationError) as exc_info:
            repo_manager.clone_repository("owner/repo")

        assert "Authentication failed" in str(exc_info.value)

    @patch("subprocess.run")
    def test_clone_repository_gh_not_installed(self, mock_run, repo_manager):
        """Test when gh CLI is not installed."""
        mock_run.side_effect = FileNotFoundError()

        with pytest.raises(CloneError) as exc_info:
            repo_manager.clone_repository("owner/repo")

        assert "not installed" in str(exc_info.value)

    @patch("subprocess.run")
    def test_clone_repository_already_exists(self, mock_run, repo_manager, temp_dir):
        """Test cloning when repository already exists."""
        mock_run.return_value = Mock(returncode=0)

        existing_repo = temp_dir / "repo"
        existing_repo.mkdir()
        (existing_repo / ".git").mkdir()

        result = repo_manager.clone_repository("owner/repo")
        assert result == existing_repo

        assert mock_run.call_count == 1

    @patch("subprocess.run")
    def test_clone_repository_path_exists_not_repo(self, mock_run, repo_manager, temp_dir):
        """Test cloning when path exists but is not a repository."""
        mock_run.return_value = Mock(returncode=0)

        existing_path = temp_dir / "repo"
        existing_path.mkdir()

        with pytest.raises(CloneError) as exc_info:
            repo_manager.clone_repository("owner/repo")

        assert "not a git repository" in str(exc_info.value)

    def test_extract_repo_name_github_url(self, repo_manager):
        """Test extracting repo name from GitHub URL."""
        assert repo_manager._extract_repo_name("https://github.com/owner/repo") == "repo"
        assert repo_manager._extract_repo_name("https://github.com/owner/repo.git") == "repo"
        assert repo_manager._extract_repo_name("https://github.com/owner/repo/") == "repo"

    def test_extract_repo_name_owner_repo(self, repo_manager):
        """Test extracting repo name from owner/repo format."""
        assert repo_manager._extract_repo_name("owner/repo") == "repo"
        assert repo_manager._extract_repo_name("org/project-name") == "project-name"

    def test_extract_repo_name_simple(self, repo_manager):
        """Test extracting repo name from simple name."""
        assert repo_manager._extract_repo_name("myrepo") == "myrepo"

    def test_is_git_repository_true(self, repo_manager, temp_dir):
        """Test checking if path is a git repository."""
        repo_dir = temp_dir / "repo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()

        assert repo_manager._is_git_repository(repo_dir) is True

    def test_is_git_repository_false(self, repo_manager, temp_dir):
        """Test checking if path is not a git repository."""
        non_repo = temp_dir / "not-repo"
        non_repo.mkdir()

        assert repo_manager._is_git_repository(non_repo) is False
        assert repo_manager._is_git_repository(temp_dir / "nonexistent") is False

    @patch("subprocess.run")
    def test_get_repository_info(self, mock_run, repo_manager, temp_dir):
        """Test getting repository information."""
        repo_dir = temp_dir / "repo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()

        mock_run.side_effect = [
            Mock(returncode=0, stdout="https://github.com/owner/repo.git\n"),
            Mock(returncode=0, stdout="main\n"),
        ]

        info = repo_manager.get_repository_info(repo_dir)

        assert info["path"] == str(repo_dir)
        assert info["name"] == "repo"
        assert info["remote_url"] == "https://github.com/owner/repo.git"
        assert info["current_branch"] == "main"

    def test_get_repository_info_not_repo(self, repo_manager, temp_dir):
        """Test getting info for non-repository."""
        non_repo = temp_dir / "not-repo"
        non_repo.mkdir()

        with pytest.raises(RepositoryError) as exc_info:
            repo_manager.get_repository_info(non_repo)

        assert "Not a git repository" in str(exc_info.value)
