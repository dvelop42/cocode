"""GitHub repository metadata fetcher via gh CLI."""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class RepositoryError(Exception):
    """Repository operation related errors."""

    pass


@dataclass
class RepositoryMetadata:
    """Repository metadata from GitHub."""

    owner: str
    name: str
    full_name: str
    default_branch: str
    description: str | None = None
    is_private: bool = False
    is_fork: bool = False
    parent_full_name: str | None = None
    clone_url: str | None = None
    ssh_url: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    language: str | None = None
    topics: list[str] = field(default_factory=list)
    has_issues: bool = True
    has_wiki: bool = True
    has_discussions: bool = False
    is_archived: bool = False
    is_disabled: bool = False
    raw_data: dict[str, Any] = field(default_factory=dict)


class RepositoryMetadataFetcher:
    """Fetches and caches repository metadata via gh CLI."""

    # Cache duration (default: 5 minutes)
    DEFAULT_CACHE_TTL = timedelta(minutes=5)

    def __init__(self, cache_dir: Path | None = None, cache_ttl: timedelta | None = None):
        """Initialize repository metadata fetcher.

        Args:
            cache_dir: Directory for caching metadata. Defaults to .cocode/cache
            cache_ttl: Cache time-to-live. Defaults to 5 minutes
        """
        self.cache_dir = cache_dir or Path(".cocode/cache")
        self.cache_ttl = cache_ttl or self.DEFAULT_CACHE_TTL
        self._cache: dict[str, tuple[RepositoryMetadata, datetime]] = {}

    def get_metadata(
        self, repo: str | None = None, force_refresh: bool = False
    ) -> RepositoryMetadata:
        """Get repository metadata, using cache if available.

        Args:
            repo: Repository in format owner/name. If None, uses current repo
            force_refresh: Force refresh from GitHub, ignoring cache

        Returns:
            RepositoryMetadata object

        Raises:
            RepositoryError: If fetching metadata fails
        """
        # If no repo specified, detect from current directory
        if repo is None:
            repo = self._detect_current_repo()

        # Check memory cache first
        if not force_refresh and repo in self._cache:
            metadata, cached_at = self._cache[repo]
            if datetime.now() - cached_at < self.cache_ttl:
                logger.debug(f"Using cached metadata for {repo}")
                return metadata

        # Check disk cache
        if not force_refresh:
            cached_metadata = self._load_from_disk_cache(repo)
            if cached_metadata:
                self._cache[repo] = (cached_metadata, datetime.now())
                return cached_metadata

        # Fetch fresh metadata
        logger.debug(f"Fetching fresh metadata for {repo}")
        metadata = self._fetch_from_github(repo)

        # Update caches
        self._cache[repo] = (metadata, datetime.now())
        self._save_to_disk_cache(repo, metadata)

        return metadata

    def get_default_branch(self, repo: str | None = None) -> str:
        """Get the default branch for a repository.

        Args:
            repo: Repository in format owner/name. If None, uses current repo

        Returns:
            Default branch name (e.g., 'main', 'master')

        Raises:
            RepositoryError: If fetching metadata fails
        """
        metadata = self.get_metadata(repo)
        return metadata.default_branch

    def clear_cache(self, repo: str | None = None) -> None:
        """Clear cached metadata.

        Args:
            repo: Repository to clear cache for. If None, clears all cache
        """
        if repo:
            # Clear specific repo from memory cache
            self._cache.pop(repo, None)

            # Clear from disk cache
            cache_file = self._get_cache_file_path(repo)
            if cache_file.exists():
                cache_file.unlink()
                logger.debug(f"Cleared cache for {repo}")
        else:
            # Clear all cache
            self._cache.clear()

            # Clear disk cache directory
            if self.cache_dir.exists():
                for cache_file in self.cache_dir.glob("*.json"):
                    cache_file.unlink()
                logger.debug("Cleared all repository cache")

    def _detect_current_repo(self) -> str:
        """Detect repository from current git directory.

        Returns:
            Repository in owner/name format

        Raises:
            RepositoryError: If detection fails
        """
        try:
            # Get remote URL
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            )
            url = result.stdout.strip()

            # Parse owner/name from URL
            # Handle both HTTPS and SSH URLs
            if url.startswith("https://github.com/"):
                # https://github.com/owner/repo.git
                repo_path = url.replace("https://github.com/", "").rstrip("/")
            elif url.startswith("git@github.com:"):
                # git@github.com:owner/repo.git
                repo_path = url.replace("git@github.com:", "").rstrip("/")
            else:
                raise RepositoryError(f"Unsupported remote URL format: {url}")

            # Remove .git suffix if present
            if repo_path.endswith(".git"):
                repo_path = repo_path[:-4]

            # Validate format
            if "/" not in repo_path or repo_path.count("/") != 1:
                raise RepositoryError(f"Invalid repository format: {repo_path}")

            logger.debug(f"Detected repository: {repo_path}")
            return repo_path

        except subprocess.CalledProcessError as e:
            raise RepositoryError(f"Failed to detect repository: {e}") from e
        except subprocess.TimeoutExpired:
            raise RepositoryError("Timeout detecting repository") from None
        except FileNotFoundError:
            raise RepositoryError("git command not found") from None

    def _fetch_from_github(self, repo: str) -> RepositoryMetadata:
        """Fetch repository metadata from GitHub using gh CLI.

        Args:
            repo: Repository in format owner/name

        Returns:
            RepositoryMetadata object

        Raises:
            RepositoryError: If fetching fails
        """
        try:
            # Use gh repo view with JSON output
            result = subprocess.run(
                ["gh", "repo", "view", repo, "--json", self._get_json_fields()],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )

            # Parse JSON response
            data = json.loads(result.stdout)

            # Extract owner and name
            owner = data.get("owner", {}).get("login", "")
            name = data.get("name", "")

            if not owner or not name:
                # Fallback to parsing from nameWithOwner or input
                full_name = data.get("nameWithOwner", repo)
                if "/" in full_name:
                    owner, name = full_name.split("/", 1)
                else:
                    raise RepositoryError("Could not parse owner/name from response")

            # Create metadata object
            metadata = RepositoryMetadata(
                owner=owner,
                name=name,
                full_name=f"{owner}/{name}",
                default_branch=data.get("defaultBranchRef", {}).get("name", "main"),
                description=data.get("description"),
                is_private=data.get("isPrivate", False),
                is_fork=data.get("isFork", False),
                parent_full_name=(
                    data.get("parent", {}).get("nameWithOwner") if data.get("parent") else None
                ),
                clone_url=data.get("url"),
                ssh_url=data.get("sshUrl"),
                created_at=data.get("createdAt"),
                updated_at=data.get("updatedAt"),
                language=data.get("primaryLanguage", {}).get("name")
                if data.get("primaryLanguage")
                else None,
                topics=[
                    topic.get("name", "")
                    for topic in (data.get("repositoryTopics") or [])
                    if isinstance(topic, dict)
                ],
                has_issues=data.get("hasIssuesEnabled", True),
                has_wiki=data.get("hasWikiEnabled", True),
                has_discussions=data.get("hasDiscussionsEnabled", False),
                is_archived=data.get("isArchived", False),
                is_disabled=False,  # Field not available in gh CLI
                raw_data=data,
            )

            logger.info(f"Fetched metadata for {repo} (default branch: {metadata.default_branch})")
            return metadata

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            raise RepositoryError(f"Failed to fetch repository metadata: {error_msg}") from e
        except subprocess.TimeoutExpired:
            raise RepositoryError("Timeout fetching repository metadata") from None
        except FileNotFoundError:
            raise RepositoryError("GitHub CLI (gh) not found") from None
        except json.JSONDecodeError as e:
            raise RepositoryError(f"Failed to parse repository response: {e}") from e
        except Exception as e:
            raise RepositoryError(f"Unexpected error fetching metadata: {e}") from e

    def _get_json_fields(self) -> str:
        """Get comma-separated list of fields to request from gh CLI."""
        return (
            "owner,name,nameWithOwner,description,defaultBranchRef,isPrivate,"
            "isFork,parent,url,sshUrl,createdAt,updatedAt,primaryLanguage,"
            "repositoryTopics,hasIssuesEnabled,hasWikiEnabled,hasDiscussionsEnabled,"
            "isArchived"
        )

    def _get_cache_file_path(self, repo: str) -> Path:
        """Get cache file path for a repository.

        Args:
            repo: Repository in format owner/name

        Returns:
            Path to cache file
        """
        # Replace / with _ for filename
        safe_name = repo.replace("/", "_")
        return self.cache_dir / f"{safe_name}.json"

    def _load_from_disk_cache(self, repo: str) -> RepositoryMetadata | None:
        """Load metadata from disk cache if valid.

        Args:
            repo: Repository in format owner/name

        Returns:
            RepositoryMetadata if cache is valid, None otherwise
        """
        cache_file = self._get_cache_file_path(repo)

        if not cache_file.exists():
            return None

        try:
            with open(cache_file) as f:
                cache_data = json.load(f)

            # Check cache expiry
            cached_at = datetime.fromisoformat(cache_data["cached_at"])
            if datetime.now() - cached_at > self.cache_ttl:
                logger.debug(f"Disk cache expired for {repo}")
                return None

            # Reconstruct metadata
            metadata_dict = cache_data["metadata"]
            metadata = RepositoryMetadata(
                owner=metadata_dict["owner"],
                name=metadata_dict["name"],
                full_name=metadata_dict["full_name"],
                default_branch=metadata_dict["default_branch"],
                description=metadata_dict.get("description"),
                is_private=metadata_dict.get("is_private", False),
                is_fork=metadata_dict.get("is_fork", False),
                parent_full_name=metadata_dict.get("parent_full_name"),
                clone_url=metadata_dict.get("clone_url"),
                ssh_url=metadata_dict.get("ssh_url"),
                created_at=metadata_dict.get("created_at"),
                updated_at=metadata_dict.get("updated_at"),
                language=metadata_dict.get("language"),
                topics=metadata_dict.get("topics", []),
                has_issues=metadata_dict.get("has_issues", True),
                has_wiki=metadata_dict.get("has_wiki", True),
                has_discussions=metadata_dict.get("has_discussions", False),
                is_archived=metadata_dict.get("is_archived", False),
                is_disabled=metadata_dict.get("is_disabled", False),
                raw_data=metadata_dict.get("raw_data", {}),
            )

            logger.debug(f"Loaded metadata from disk cache for {repo}")
            return metadata

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Invalid cache file for {repo}: {e}")
            # Remove corrupted cache file
            cache_file.unlink()
            return None
        except Exception as e:
            logger.warning(f"Failed to load cache for {repo}: {e}")
            return None

    def _save_to_disk_cache(self, repo: str, metadata: RepositoryMetadata) -> None:
        """Save metadata to disk cache.

        Args:
            repo: Repository in format owner/name
            metadata: RepositoryMetadata to cache
        """
        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        cache_file = self._get_cache_file_path(repo)

        try:
            # Prepare cache data
            cache_data = {
                "cached_at": datetime.now().isoformat(),
                "metadata": {
                    "owner": metadata.owner,
                    "name": metadata.name,
                    "full_name": metadata.full_name,
                    "default_branch": metadata.default_branch,
                    "description": metadata.description,
                    "is_private": metadata.is_private,
                    "is_fork": metadata.is_fork,
                    "parent_full_name": metadata.parent_full_name,
                    "clone_url": metadata.clone_url,
                    "ssh_url": metadata.ssh_url,
                    "created_at": metadata.created_at,
                    "updated_at": metadata.updated_at,
                    "language": metadata.language,
                    "topics": metadata.topics,
                    "has_issues": metadata.has_issues,
                    "has_wiki": metadata.has_wiki,
                    "has_discussions": metadata.has_discussions,
                    "is_archived": metadata.is_archived,
                    "is_disabled": metadata.is_disabled,
                    "raw_data": metadata.raw_data,
                },
            }

            # Write to cache file
            with open(cache_file, "w") as f:
                json.dump(cache_data, f, indent=2)

            logger.debug(f"Saved metadata to disk cache for {repo}")

        except Exception as e:
            # Cache write failures are non-fatal
            logger.warning(f"Failed to save cache for {repo}: {e}")


# Convenience function for simple use cases
def get_default_branch(repo: str | None = None) -> str:
    """Get the default branch for a repository.

    Args:
        repo: Repository in format owner/name. If None, uses current repo

    Returns:
        Default branch name (e.g., 'main', 'master')

    Raises:
        RepositoryError: If fetching metadata fails
    """
    fetcher = RepositoryMetadataFetcher()
    return fetcher.get_default_branch(repo)
