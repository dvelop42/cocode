"""Shared pytest fixtures."""

import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest


@pytest.fixture
def temp_repo():
    """Create a temporary git repository for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=repo_path, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, check=True)

        # Create initial commit
        (repo_path / "README.md").write_text("# Test Repository")
        subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, check=True)

        yield repo_path


@pytest.fixture
def mock_issue():
    """Create a mock GitHub issue."""
    return {
        "number": 123,
        "title": "Fix authentication bug",
        "body": "Users cannot log in with OAuth when using Chrome",
        "url": "https://github.com/test/repo/issues/123",
        "state": "open",
        "labels": ["bug", "high-priority"]
    }


@pytest.fixture
def temp_config_dir():
    """Create a temporary config directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / ".cocode"
        config_path.mkdir()
        yield config_path


@pytest.fixture
def mock_agent_env():
    """Create mock agent environment variables."""
    return {
        "COCODE_REPO_PATH": "/tmp/test-repo",
        "COCODE_ISSUE_NUMBER": "123",
        "COCODE_ISSUE_URL": "https://github.com/test/repo/issues/123",
        "COCODE_ISSUE_BODY_FILE": "/tmp/issue_123.txt",
        "COCODE_READY_MARKER": "cocode ready for check"
    }


@pytest.fixture
def mock_subprocess_run():
    """Mock subprocess.run for testing command execution."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Success",
            stderr=""
        )
        yield mock_run


@pytest.fixture
def sample_cocode_config():
    """Sample cocode configuration."""
    return {
        "version": "1.0",
        "agents": {
            "claude-code": {
                "command": "claude-code",
                "args": ["--repo", "{repo_path}", "--issue", "{issue_number}"],
                "timeout": 900,
                "enabled": True
            },
            "codex": {
                "command": "codex-cli",
                "args": ["fix", "--issue={issue_number}"],
                "timeout": 600,
                "enabled": False
            }
        },
        "performance": {
            "max_concurrent_agents": 3,
            "default_timeout": 900,
            "polling_interval": 5
        }
    }


@pytest.fixture
def mock_gh_cli():
    """Mock GitHub CLI responses."""
    with patch("subprocess.run") as mock_run:
        def side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])

            if "gh" in cmd and "auth" in cmd and "status" in cmd:
                return Mock(returncode=0, stdout="Logged in as test-user")
            elif "gh" in cmd and "issue" in cmd and "view" in cmd:
                return Mock(
                    returncode=0,
                    stdout=json.dumps({
                        "number": 123,
                        "title": "Test Issue",
                        "body": "Issue body"
                    })
                )
            elif "gh" in cmd and "pr" in cmd and "create" in cmd:
                return Mock(
                    returncode=0,
                    stdout="https://github.com/test/repo/pull/456"
                )
            return Mock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = side_effect
        yield mock_run
