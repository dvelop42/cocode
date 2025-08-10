"""Tests for repository metadata fetcher."""

import json
import subprocess
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from cocode.github.repository import (
    RepositoryError,
    RepositoryMetadata,
    RepositoryMetadataFetcher,
    get_default_branch,
)


class TestRepositoryMetadata:
    """Tests for RepositoryMetadata dataclass."""

    def test_repository_metadata_creation(self):
        """Test creating a RepositoryMetadata instance."""
        metadata = RepositoryMetadata(
            owner="octocat",
            name="hello-world",
            full_name="octocat/hello-world",
            default_branch="main",
            description="My first repository",
            is_private=False,
            is_fork=False,
        )

        assert metadata.owner == "octocat"
        assert metadata.name == "hello-world"
        assert metadata.full_name == "octocat/hello-world"
        assert metadata.default_branch == "main"
        assert metadata.description == "My first repository"
        assert metadata.is_private is False
        assert metadata.is_fork is False
        assert metadata.topics == []

    def test_repository_metadata_with_all_fields(self):
        """Test RepositoryMetadata with all optional fields."""
        metadata = RepositoryMetadata(
            owner="octocat",
            name="hello-world",
            full_name="octocat/hello-world",
            default_branch="develop",
            description="Test repo",
            is_private=True,
            is_fork=True,
            parent_full_name="original/hello-world",
            clone_url="https://github.com/octocat/hello-world.git",
            ssh_url="git@github.com:octocat/hello-world.git",
            created_at="2020-01-01T00:00:00Z",
            updated_at="2023-12-01T00:00:00Z",
            language="Python",
            topics=["python", "cli", "automation"],
            has_issues=True,
            has_wiki=False,
            has_discussions=True,
            is_archived=False,
            is_disabled=False,
            raw_data={"extra": "data"},
        )

        assert metadata.is_private is True
        assert metadata.is_fork is True
        assert metadata.parent_full_name == "original/hello-world"
        assert metadata.language == "Python"
        assert metadata.topics == ["python", "cli", "automation"]
        assert metadata.has_wiki is False
        assert metadata.has_discussions is True


class TestRepositoryMetadataFetcher:
    """Tests for RepositoryMetadataFetcher."""

    @pytest.fixture
    def fetcher(self, tmp_path):
        """Create a fetcher with temp cache directory."""
        cache_dir = tmp_path / "cache"
        return RepositoryMetadataFetcher(cache_dir=cache_dir, cache_ttl=timedelta(minutes=5))

    @pytest.fixture
    def mock_gh_response(self):
        """Mock response from gh repo view."""
        return {
            "owner": {"login": "octocat"},
            "name": "hello-world",
            "nameWithOwner": "octocat/hello-world",
            "description": "My first repository on GitHub!",
            "defaultBranchRef": {"name": "main"},
            "isPrivate": False,
            "isFork": False,
            "parent": None,
            "url": "https://github.com/octocat/hello-world",
            "sshUrl": "git@github.com:octocat/hello-world.git",
            "createdAt": "2020-01-01T00:00:00Z",
            "updatedAt": "2023-12-01T00:00:00Z",
            "primaryLanguage": {"name": "Python"},
            "repositoryTopics": [{"name": "python"}, {"name": "cli"}],
            "hasIssuesEnabled": True,
            "hasWikiEnabled": True,
            "hasDiscussionsEnabled": False,
            "isArchived": False,
            "isDisabled": False,
        }

    def test_detect_current_repo_https(self, fetcher):
        """Test detecting repository from HTTPS remote URL."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = "https://github.com/octocat/hello-world.git\n"
            mock_run.return_value.returncode = 0

            repo = fetcher._detect_current_repo()

            assert repo == "octocat/hello-world"
            mock_run.assert_called_once()

    def test_detect_current_repo_ssh(self, fetcher):
        """Test detecting repository from SSH remote URL."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = "git@github.com:octocat/hello-world.git\n"
            mock_run.return_value.returncode = 0

            repo = fetcher._detect_current_repo()

            assert repo == "octocat/hello-world"

    def test_detect_current_repo_no_git(self, fetcher):
        """Test error when git command fails."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, ["git"])

            with pytest.raises(RepositoryError, match="Failed to detect repository"):
                fetcher._detect_current_repo()

    def test_detect_current_repo_invalid_url(self, fetcher):
        """Test error with unsupported remote URL format."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = "https://gitlab.com/user/repo.git\n"
            mock_run.return_value.returncode = 0

            with pytest.raises(RepositoryError, match="Unsupported remote URL format"):
                fetcher._detect_current_repo()

    def test_fetch_from_github_success(self, fetcher, mock_gh_response):
        """Test successful fetch from GitHub."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = json.dumps(mock_gh_response)
            mock_run.return_value.returncode = 0

            metadata = fetcher._fetch_from_github("octocat/hello-world")

            assert metadata.owner == "octocat"
            assert metadata.name == "hello-world"
            assert metadata.full_name == "octocat/hello-world"
            assert metadata.default_branch == "main"
            assert metadata.description == "My first repository on GitHub!"
            assert metadata.language == "Python"
            assert metadata.topics == ["python", "cli"]

    def test_fetch_from_github_command_error(self, fetcher):
        """Test error when gh command fails."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                1, ["gh"], stderr="repository not found"
            )

            with pytest.raises(RepositoryError, match="Failed to fetch repository metadata"):
                fetcher._fetch_from_github("invalid/repo")

    def test_fetch_from_github_timeout(self, fetcher):
        """Test timeout when fetching from GitHub."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(["gh"], 10)

            with pytest.raises(RepositoryError, match="Timeout fetching repository metadata"):
                fetcher._fetch_from_github("octocat/hello-world")

    def test_fetch_from_github_no_gh(self, fetcher):
        """Test error when gh CLI is not installed."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            with pytest.raises(RepositoryError, match="GitHub CLI .* not found"):
                fetcher._fetch_from_github("octocat/hello-world")

    def test_fetch_from_github_invalid_json(self, fetcher):
        """Test error with invalid JSON response."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = "invalid json"
            mock_run.return_value.returncode = 0

            with pytest.raises(RepositoryError, match="Failed to parse repository response"):
                fetcher._fetch_from_github("octocat/hello-world")

    def test_get_metadata_with_cache(self, fetcher, mock_gh_response):
        """Test get_metadata uses cache on second call."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = json.dumps(mock_gh_response)
            mock_run.return_value.returncode = 0

            # First call - should fetch from GitHub
            metadata1 = fetcher.get_metadata("octocat/hello-world")
            assert metadata1.default_branch == "main"
            assert mock_run.call_count == 1

            # Second call - should use cache
            metadata2 = fetcher.get_metadata("octocat/hello-world")
            assert metadata2.default_branch == "main"
            assert mock_run.call_count == 1  # No additional calls

            # Same object from cache
            assert metadata1 is metadata2

    def test_get_metadata_force_refresh(self, fetcher, mock_gh_response):
        """Test force_refresh bypasses cache."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = json.dumps(mock_gh_response)
            mock_run.return_value.returncode = 0

            # First call
            fetcher.get_metadata("octocat/hello-world")
            assert mock_run.call_count == 1

            # Second call with force_refresh
            fetcher.get_metadata("octocat/hello-world", force_refresh=True)
            assert mock_run.call_count == 2

    def test_get_metadata_cache_expiry(self, fetcher, mock_gh_response):
        """Test cache expires after TTL."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = json.dumps(mock_gh_response)
            mock_run.return_value.returncode = 0

            # First call
            fetcher.get_metadata("octocat/hello-world")
            assert mock_run.call_count == 1

            # Simulate time passing beyond TTL
            with patch("cocode.github.repository.datetime") as mock_datetime:
                mock_datetime.now.return_value = datetime.now() + timedelta(minutes=10)

                # Should fetch again due to expired cache
                fetcher.get_metadata("octocat/hello-world")
                assert mock_run.call_count == 2

    def test_get_metadata_no_repo_specified(self, fetcher, mock_gh_response):
        """Test get_metadata with no repo (uses current)."""
        with patch.object(fetcher, "_detect_current_repo") as mock_detect:
            mock_detect.return_value = "octocat/hello-world"

            with patch("subprocess.run") as mock_run:
                mock_run.return_value.stdout = json.dumps(mock_gh_response)
                mock_run.return_value.returncode = 0

                metadata = fetcher.get_metadata()

                assert metadata.full_name == "octocat/hello-world"
                mock_detect.assert_called_once()

    def test_get_default_branch(self, fetcher, mock_gh_response):
        """Test get_default_branch method."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = json.dumps(mock_gh_response)
            mock_run.return_value.returncode = 0

            branch = fetcher.get_default_branch("octocat/hello-world")

            assert branch == "main"

    def test_disk_cache_save_and_load(self, fetcher, tmp_path):
        """Test saving and loading from disk cache."""
        metadata = RepositoryMetadata(
            owner="octocat",
            name="hello-world",
            full_name="octocat/hello-world",
            default_branch="main",
            description="Test repo",
            topics=["python", "cli"],
        )

        # Save to disk cache
        fetcher._save_to_disk_cache("octocat/hello-world", metadata)

        # Verify file was created
        cache_file = fetcher._get_cache_file_path("octocat/hello-world")
        assert cache_file.exists()

        # Load from disk cache
        loaded = fetcher._load_from_disk_cache("octocat/hello-world")

        assert loaded is not None
        assert loaded.owner == "octocat"
        assert loaded.name == "hello-world"
        assert loaded.default_branch == "main"
        assert loaded.topics == ["python", "cli"]

    def test_disk_cache_expiry(self, fetcher, tmp_path):
        """Test disk cache expires after TTL."""
        metadata = RepositoryMetadata(
            owner="octocat",
            name="hello-world",
            full_name="octocat/hello-world",
            default_branch="main",
        )

        # Save to disk cache
        fetcher._save_to_disk_cache("octocat/hello-world", metadata)

        # Simulate expired cache
        cache_file = fetcher._get_cache_file_path("octocat/hello-world")
        with open(cache_file) as f:
            cache_data = json.load(f)

        # Set cached_at to past time
        cache_data["cached_at"] = (datetime.now() - timedelta(minutes=10)).isoformat()

        with open(cache_file, "w") as f:
            json.dump(cache_data, f)

        # Should return None due to expiry
        loaded = fetcher._load_from_disk_cache("octocat/hello-world")
        assert loaded is None

    def test_disk_cache_corrupted(self, fetcher, tmp_path):
        """Test handling of corrupted cache file."""
        cache_file = fetcher._get_cache_file_path("octocat/hello-world")
        cache_file.parent.mkdir(parents=True, exist_ok=True)

        # Write invalid JSON
        with open(cache_file, "w") as f:
            f.write("invalid json")

        # Should return None and remove corrupted file
        loaded = fetcher._load_from_disk_cache("octocat/hello-world")
        assert loaded is None
        assert not cache_file.exists()

    def test_clear_cache_specific_repo(self, fetcher):
        """Test clearing cache for specific repository."""
        metadata = RepositoryMetadata(
            owner="octocat",
            name="hello-world",
            full_name="octocat/hello-world",
            default_branch="main",
        )

        # Add to memory cache
        fetcher._cache["octocat/hello-world"] = (metadata, datetime.now())

        # Save to disk cache
        fetcher._save_to_disk_cache("octocat/hello-world", metadata)
        cache_file = fetcher._get_cache_file_path("octocat/hello-world")
        assert cache_file.exists()

        # Clear cache
        fetcher.clear_cache("octocat/hello-world")

        # Verify cleared
        assert "octocat/hello-world" not in fetcher._cache
        assert not cache_file.exists()

    def test_clear_cache_all(self, fetcher):
        """Test clearing all cache."""
        metadata1 = RepositoryMetadata(
            owner="octocat",
            name="hello-world",
            full_name="octocat/hello-world",
            default_branch="main",
        )
        metadata2 = RepositoryMetadata(
            owner="user",
            name="project",
            full_name="user/project",
            default_branch="develop",
        )

        # Add to caches
        fetcher._cache["octocat/hello-world"] = (metadata1, datetime.now())
        fetcher._cache["user/project"] = (metadata2, datetime.now())

        fetcher._save_to_disk_cache("octocat/hello-world", metadata1)
        fetcher._save_to_disk_cache("user/project", metadata2)

        # Clear all
        fetcher.clear_cache()

        # Verify all cleared
        assert len(fetcher._cache) == 0
        assert not fetcher._get_cache_file_path("octocat/hello-world").exists()
        assert not fetcher._get_cache_file_path("user/project").exists()

    def test_get_cache_file_path(self, fetcher):
        """Test cache file path generation."""
        path = fetcher._get_cache_file_path("octocat/hello-world")
        assert path.name == "octocat_hello-world.json"
        assert path.parent == fetcher.cache_dir

    def test_fetch_fork_repository(self, fetcher):
        """Test fetching metadata for a forked repository."""
        mock_response = {
            "owner": {"login": "myuser"},
            "name": "forked-repo",
            "nameWithOwner": "myuser/forked-repo",
            "defaultBranchRef": {"name": "main"},
            "isPrivate": False,
            "isFork": True,
            "parent": {"nameWithOwner": "original/forked-repo"},
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = json.dumps(mock_response)
            mock_run.return_value.returncode = 0

            metadata = fetcher._fetch_from_github("myuser/forked-repo")

            assert metadata.is_fork is True
            assert metadata.parent_full_name == "original/forked-repo"


class TestModuleFunctions:
    """Test module-level convenience functions."""

    def test_get_default_branch_function(self):
        """Test the module-level get_default_branch function with explicit repo."""
        mock_function_response = {
            "owner": {"login": "octocat"},
            "name": "hello-world",
            "nameWithOwner": "octocat/hello-world",
            "defaultBranchRef": {"name": "develop"},
        }

        with patch("cocode.github.repository.subprocess.run") as mock_run:
            mock_run.return_value.stdout = json.dumps(mock_function_response)
            mock_run.return_value.returncode = 0

            branch = get_default_branch("octocat/hello-world")

            assert branch == "develop"

    def test_get_default_branch_current_repo(self):
        """Test get_default_branch with no repo specified (auto-detect current repo)."""
        mock_current_repo_response = {
            "owner": {"login": "testuser"},
            "name": "test-repo",
            "nameWithOwner": "testuser/test-repo",
            "defaultBranchRef": {"name": "main"},
        }

        with patch("cocode.github.repository.subprocess.run") as mock_run:
            # Setup side effect for multiple calls
            def side_effect(*args, **kwargs):
                cmd = args[0]
                if cmd[0:3] == ["git", "remote", "get-url"]:
                    result = Mock()
                    result.stdout = "https://github.com/testuser/test-repo.git\n"
                    result.returncode = 0
                    return result
                else:  # gh repo view
                    result = Mock()
                    result.stdout = json.dumps(mock_current_repo_response)
                    result.returncode = 0
                    return result

            mock_run.side_effect = side_effect

            branch = get_default_branch()

            assert branch == "main"
