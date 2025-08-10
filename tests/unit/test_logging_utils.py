"""Tests for logging utilities: SecretRedactor and setup_logging."""

from cocode.utils.logging import SecretRedactor, setup_logging


def test_secret_redactor_common_patterns():
    r = SecretRedactor()
    text = (
        "token ghp_" + ("a" * 36) + " hello "
        "openai sk-" + ("b" * 48) + " "
        "bearer Bearer ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789=="
    )
    redacted = r.redact(text)
    assert "gh*_***" in redacted
    assert "sk-***" in redacted
    assert "Bearer ***" in redacted


def test_setup_logging_invocation():
    # Should not raise and returns None; actual global level may already be configured
    assert setup_logging("DEBUG") is None
