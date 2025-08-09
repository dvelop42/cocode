"""Exit codes for cocode following ADR-003."""

from enum import IntEnum


class ExitCode(IntEnum):
    """Standard exit codes for agent operations per ADR-003."""
    
    SUCCESS = 0  # Success, check for ready marker
    GENERAL_ERROR = 1  # General error
    INVALID_CONFIG = 2  # Invalid configuration
    MISSING_DEPS = 3  # Missing dependencies
    TIMEOUT = 124  # Agent exceeded time limit
    INTERRUPTED = 130  # User cancelled operation