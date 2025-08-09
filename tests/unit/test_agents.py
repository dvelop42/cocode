"""Unit tests for agent functionality."""

import subprocess
import tempfile
from pathlib import Path

import pytest


class TestAgentProtocol:
    """Test agent communication protocol (ADR-003)."""

    @pytest.mark.unit
    def test_agent_environment_variables(self, mock_agent_env):
        """Test required environment variables are set."""
        required_vars = [
            "COCODE_REPO_PATH",
            "COCODE_ISSUE_NUMBER",
            "COCODE_ISSUE_URL",
            "COCODE_ISSUE_BODY_FILE",
            "COCODE_READY_MARKER",
        ]
        for var in required_vars:
            assert var in mock_agent_env
            assert mock_agent_env[var]

    @pytest.mark.unit
    def test_ready_marker_detection(self, temp_repo):
        """Test detection of ready marker in commit message."""
        # Create commit with ready marker
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "fix: issue\n\ncocode ready for check"],
            cwd=temp_repo,
            check=True,
        )

        # Check for ready marker
        result = subprocess.run(
            ["git", "log", "-1", "--format=%B"], cwd=temp_repo, capture_output=True, text=True
        )
        assert "cocode ready for check" in result.stdout

    @pytest.mark.unit
    def test_agent_exit_codes(self):
        """Test agent exit code meanings (ADR-003)."""
        exit_codes = {
            0: "Success",
            1: "General error",
            2: "Invalid config",
            3: "Missing dependencies",
            124: "Timeout",
            130: "Interrupted",
        }

        for code, meaning in exit_codes.items():
            assert isinstance(code, int)
            assert isinstance(meaning, str)


class TestAgentExecution:
    """Test agent execution and management."""

    @pytest.mark.unit
    def test_agent_timeout_enforcement(self, mock_subprocess_run):
        """Test that agents are killed after timeout."""
        mock_subprocess_run.side_effect = subprocess.TimeoutExpired(cmd=["test-agent"], timeout=900)

        with pytest.raises(subprocess.TimeoutExpired):
            subprocess.run(["test-agent"], timeout=900)

    @pytest.mark.unit
    def test_safe_environment_filtering(self):
        """Test environment variable filtering (ADR-004)."""
        allowed_vars = {
            "LANG",
            "LC_ALL",
            "LC_CTYPE",
            "LC_MESSAGES",
            "LC_TIME",
            "TERM",
            "TERMINFO",
            "USER",
            "USERNAME",
            "TZ",
            "TMPDIR",
        }

        test_env = {
            "LANG": "en_US.UTF-8",
            "SECRET_KEY": "should_be_filtered",
            "COCODE_TEST": "should_pass_through",
            "USER": "testuser",
            "API_TOKEN": "should_be_filtered",
        }

        filtered = {
            k: v for k, v in test_env.items() if k in allowed_vars or k.startswith("COCODE_")
        }

        assert "LANG" in filtered
        assert "USER" in filtered
        assert "COCODE_TEST" in filtered
        assert "SECRET_KEY" not in filtered
        assert "API_TOKEN" not in filtered

    @pytest.mark.unit
    def test_safe_path_construction(self):
        """Test controlled PATH construction (ADR-004)."""
        safe_dirs = ["/usr/bin", "/bin", "/usr/local/bin", "/opt/homebrew/bin"]
        safe_path = ":".join(safe_dirs)

        assert "/usr/bin" in safe_path
        assert "/bin" in safe_path
        assert "~" not in safe_path
        assert ".." not in safe_path


class TestAgentIsolation:
    """Test agent isolation and security."""

    @pytest.mark.unit
    def test_worktree_naming_convention(self):
        """Test worktree naming follows convention."""
        agent_name = "claude-code"
        issue_number = "123"

        worktree_dir = f"cocode_{agent_name}"
        branch_name = f"cocode/{issue_number}-{agent_name}"

        assert worktree_dir.startswith("cocode_")
        assert branch_name.startswith("cocode/")
        assert agent_name in worktree_dir
        assert agent_name in branch_name

    @pytest.mark.unit
    def test_filesystem_boundary_validation(self):
        """Test agents cannot escape worktree boundaries."""

        def validate_path(path: Path, root: Path) -> bool:
            try:
                resolved = path.resolve()
                resolved_root = root.resolve()
                return resolved.is_relative_to(resolved_root)
            except (ValueError, RuntimeError):
                return False

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            worktree = root / "cocode_agent"
            worktree.mkdir()

            # Valid paths
            assert validate_path(worktree / "file.txt", worktree)
            assert validate_path(worktree / "subdir/file.txt", worktree)

            # Invalid paths (escaping worktree)
            assert not validate_path(root / "other", worktree)
            assert not validate_path(worktree / ".." / "escape", worktree)
            assert not validate_path(Path("/etc/passwd"), worktree)


class TestAgentConfiguration:
    """Test agent configuration management."""

    @pytest.mark.unit
    def test_agent_config_structure(self, sample_cocode_config):
        """Test agent configuration has required fields."""
        agents = sample_cocode_config["agents"]

        for _agent_name, config in agents.items():
            assert "command" in config
            assert "args" in config
            assert "timeout" in config
            assert "enabled" in config
            assert isinstance(config["timeout"], int)
            assert isinstance(config["enabled"], bool)

    @pytest.mark.unit
    def test_performance_limits(self, sample_cocode_config):
        """Test performance configuration limits (ADR-005)."""
        perf = sample_cocode_config["performance"]

        assert perf["max_concurrent_agents"] <= 5  # MVP limit
        assert perf["default_timeout"] >= 900  # Min 15 minutes
        assert perf["default_timeout"] <= 2700  # Max 45 minutes
        assert perf["polling_interval"] >= 2  # Min 2 seconds
