"""Codex CLI agent implementation."""

import logging
import os
import shutil
from pathlib import Path

from cocode.agents.default import GitBasedAgent

logger = logging.getLogger(__name__)


class CodexCliAgent(GitBasedAgent):
    """Agent implementation for Codex CLI.

    Codex CLI is an AI-powered code generation tool that can analyze
    issues and generate fixes by making commits.

    How it works:
        1. Cocode sets up standard COCODE_* environment variables for issue context
        2. Codex CLI reads its own authentication from environment (CODEX_API_KEY, etc.)
        3. Codex CLI executes in the worktree directory and makes commits

    Environment variables set by cocode:
        - COCODE_REPO_PATH: Path to the git worktree
        - COCODE_ISSUE_NUMBER: GitHub issue number
        - COCODE_ISSUE_BODY_FILE: Path to file containing issue description
        - COCODE_READY_MARKER: String to include in commit message when done

    Authentication (handled by Codex CLI directly):
        - CODEX_API_KEY or OPENAI_API_KEY: API authentication
        - CODEX_AUTH_TOKEN: Authentication token
        - CODEX_MODEL: Model selection (optional)
        - CODEX_TEMPERATURE: Temperature setting (optional)
        - CODEX_MAX_TOKENS: Max tokens setting (optional)

    Command executed:
        codex fix --issue-file $COCODE_ISSUE_BODY_FILE --issue-number $COCODE_ISSUE_NUMBER \\
                  --no-interactive --commit-marker $COCODE_READY_MARKER

    The CLI will read the issue from COCODE_ISSUE_BODY_FILE and make
    commits in the worktree at COCODE_REPO_PATH. When ready, it includes
    the COCODE_READY_MARKER in its final commit message.
    """

    def __init__(self) -> None:
        """Initialize Codex CLI agent."""
        super().__init__("codex-cli")
        self.command_path: str | None = None

    def validate_environment(self) -> bool:
        """Check if Codex CLI is available."""
        # Check for 'codex' command
        self.command_path = shutil.which("codex")

        if not self.command_path:
            logger.warning(
                "Codex CLI not found. Please install Codex CLI and ensure it's in your PATH"
            )
            return False

        logger.debug(f"Found Codex CLI at: {self.command_path}")
        return True

    def prepare_environment(
        self, worktree_path: Path, issue_number: int, issue_body: str
    ) -> dict[str, str]:
        """Prepare environment variables for Codex CLI.

        Codex CLI uses standard COCODE_* environment variables which are
        already set by the runner. Codex CLI will handle its own
        authentication environment variables (CODEX_API_KEY, OPENAI_API_KEY, etc.)
        """
        # No additional environment setup needed
        # Codex CLI will read its own auth variables from the environment
        return {}

    def get_command(self) -> list[str]:
        """Get the command to execute Codex CLI.

        Codex CLI should be invoked with specific arguments to:
        1. Read the issue from COCODE_ISSUE_BODY_FILE
        2. Work in the COCODE_REPO_PATH worktree
        3. Make commits with the COCODE_READY_MARKER

        The exact command structure depends on Codex CLI's interface.
        """
        if not self.command_path:
            # Fallback if validate wasn't called
            self.command_path = shutil.which("codex")
            if not self.command_path:
                raise RuntimeError(
                    "Codex CLI not found. Please install Codex CLI and verify it's in your PATH"
                )

        # Build command based on Codex CLI structure
        # This assumes Codex CLI has a 'fix' or similar subcommand
        # and can read issue from a file
        command: list[str] = [
            self.command_path,
            "fix",  # Subcommand for fixing issues
            "--issue-file",  # Flag to specify issue file
            os.environ.get("COCODE_ISSUE_BODY_FILE", ""),  # Issue file path
            "--issue-number",  # Flag to specify issue number
            os.environ.get("COCODE_ISSUE_NUMBER", ""),  # Issue number
            "--no-interactive",  # Don't prompt for user input
            "--commit-marker",  # Flag to specify ready marker
            os.environ.get("COCODE_READY_MARKER", "cocode ready for check"),  # Ready marker
        ]

        # Filter out empty values in case environment variables aren't set
        command = [arg for arg in command if arg]

        logger.debug(f"Codex CLI command: {' '.join(command)}")
        return command

    def handle_error(self, exit_code: int, output: str) -> str:
        """Handle Codex CLI specific error codes and messages.

        Args:
            exit_code: The exit code from Codex CLI
            output: The output from Codex CLI

        Returns:
            A user-friendly error message
        """
        error_messages = {
            1: "Codex CLI encountered a general error",
            2: "Invalid configuration or missing required environment variables",
            3: "Missing dependencies - check Codex CLI installation",
            124: "Codex CLI execution timed out",
            130: "Codex CLI was interrupted by user",
        }

        base_msg = error_messages.get(exit_code, f"Codex CLI failed with exit code {exit_code}")

        # Look for specific error patterns in output
        if "authentication" in output.lower() or "api key" in output.lower():
            return f"{base_msg}: Authentication failed. Check CODEX_API_KEY or OPENAI_API_KEY"
        elif "rate limit" in output.lower():
            return f"{base_msg}: Rate limit exceeded. Please wait before retrying"
        elif "network" in output.lower() or "connection" in output.lower():
            return f"{base_msg}: Network error. Check your internet connection"
        elif "permission" in output.lower():
            return f"{base_msg}: Permission denied. Check file permissions in worktree"
        elif "model" in output.lower() and "not found" in output.lower():
            return f"{base_msg}: Model not found. Check CODEX_MODEL environment variable"
        elif "token" in output.lower() and "limit" in output.lower():
            return f"{base_msg}: Token limit exceeded. Try reducing CODEX_MAX_TOKENS"

        return base_msg
