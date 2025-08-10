"""Claude Code agent implementation."""

import logging
import os
import shutil
from pathlib import Path

from cocode.agents.default import GitBasedAgent

logger = logging.getLogger(__name__)


class ClaudeCodeAgent(GitBasedAgent):
    """Agent implementation for Claude Code CLI.

    Claude Code is Anthropic's official CLI for Claude that can be used
    to fix GitHub issues by analyzing code and making commits.
    """

    def __init__(self) -> None:
        """Initialize Claude Code agent."""
        super().__init__("claude-code")
        self.command_path: str | None = None

    def validate_environment(self) -> bool:
        """Check if Claude Code CLI is available."""
        # Check for 'claude' command (the actual CLI name)
        self.command_path = shutil.which("claude")

        if not self.command_path:
            logger.warning(
                "Claude Code CLI not found. Install from: https://github.com/anthropics/claude-code"
            )
            return False

        logger.debug(f"Found Claude Code at: {self.command_path}")
        return True

    def prepare_environment(
        self, worktree_path: Path, issue_number: int, issue_body: str
    ) -> dict[str, str]:
        """Prepare environment variables for Claude Code.

        Claude Code uses standard COCODE_* environment variables which are
        already set by the runner. We just need to pass through any
        Claude-specific environment variables if they exist.
        """
        env = {}

        # Pass through Claude-specific environment variables if present
        claude_env_vars = [
            "CLAUDE_API_KEY",  # If using API key auth
            "ANTHROPIC_API_KEY",  # Alternative API key var
            "CLAUDE_CODE_OAUTH_TOKEN",  # OAuth token for authentication
        ]

        for var in claude_env_vars:
            if var in os.environ:
                env[var] = os.environ[var]
                logger.debug(f"Passing through {var} to Claude Code")

        return env

    def get_command(self) -> list[str]:
        """Get the command to execute Claude Code.

        Claude Code should be invoked with specific arguments to:
        1. Read the issue from COCODE_ISSUE_BODY_FILE
        2. Work in the COCODE_REPO_PATH worktree
        3. Make commits with the COCODE_READY_MARKER

        The exact command structure depends on Claude Code's CLI interface.
        We'll use a generic approach that should work with most agent CLIs.
        """
        if not self.command_path:
            # Fallback if validate wasn't called
            self.command_path = shutil.which("claude") or "claude"

        # Build command based on Claude Code CLI structure
        # This assumes Claude Code can take issue content via stdin or file
        # and will make commits in the current directory (worktree)
        command: list[str] = [
            self.command_path,
            "code",  # Subcommand for code operations
            "--non-interactive",  # Don't prompt for user input
        ]

        # Add issue context if Claude Code supports it
        # The agent should read from COCODE_ISSUE_BODY_FILE environment variable
        # Some agents might need explicit arguments
        issue_number = os.environ.get("COCODE_ISSUE_NUMBER")
        if issue_number:
            command.extend(["--issue", issue_number])

        # Add ready marker instruction
        # This tells Claude Code to include the marker in its final commit
        ready_marker = os.environ.get("COCODE_READY_MARKER")
        if ready_marker:
            command.extend(["--commit-suffix", ready_marker])

        logger.debug(f"Claude Code command: {' '.join(command)}")
        return command

    def handle_error(self, exit_code: int, output: str) -> str:
        """Handle Claude Code specific error codes and messages.

        Args:
            exit_code: The exit code from Claude Code
            output: The output from Claude Code

        Returns:
            A user-friendly error message
        """
        error_messages = {
            1: "Claude Code encountered a general error",
            2: "Invalid configuration or missing required environment variables",
            3: "Missing dependencies - check Claude Code installation",
            124: "Claude Code execution timed out",
            130: "Claude Code was interrupted by user",
        }

        base_msg = error_messages.get(exit_code, f"Claude Code failed with exit code {exit_code}")

        # Look for specific error patterns in output
        if "authentication" in output.lower() or "api key" in output.lower():
            return f"{base_msg}: Authentication failed. Check CLAUDE_API_KEY or run 'claude auth'"
        elif "rate limit" in output.lower():
            return f"{base_msg}: Rate limit exceeded. Please wait before retrying"
        elif "network" in output.lower() or "connection" in output.lower():
            return f"{base_msg}: Network error. Check your internet connection"
        elif "permission" in output.lower():
            return f"{base_msg}: Permission denied. Check file permissions in worktree"

        return base_msg
