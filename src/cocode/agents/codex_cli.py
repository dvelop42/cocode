"""Codex CLI agent implementation."""

import logging
import os
import shutil
import subprocess
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
        self.cli_style: str | None = None  # 'standard' or 'env-based'

    def validate_environment(self) -> bool:
        """Check if Codex CLI is available and detect its interface style."""
        # Check for 'codex' command
        self.command_path = shutil.which("codex")

        if not self.command_path:
            logger.warning(
                "Codex CLI not found. Please install Codex CLI and ensure it's in your PATH"
            )
            return False

        logger.debug(f"Found Codex CLI at: {self.command_path}")

        # Try to detect CLI interface style by checking help output
        self.cli_style = self._detect_cli_style()
        logger.debug(f"Detected Codex CLI style: {self.cli_style}")

        return True

    def _detect_cli_style(self) -> str:
        """Detect Codex CLI interface style by checking help output."""
        if not self.command_path:
            return "env-based"

        try:
            # Try to get help output to detect supported flags
            result = subprocess.run(
                [self.command_path, "--help"], capture_output=True, text=True, timeout=5
            )

            help_text = result.stdout.lower()

            # Check if it supports our expected flags
            if "fix" in help_text or "--issue-file" in help_text:
                return "standard"
            else:
                # Fallback to environment-based approach
                return "env-based"

        except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
            logger.debug(f"Could not detect CLI style: {e}")
            # Default to environment-based approach if we can't detect
            return "env-based"

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
            self.cli_style = self._detect_cli_style()

        # Validate environment variables
        self._validate_environment_variables()

        # Build command based on detected CLI style
        if self.cli_style == "standard":
            # Standard CLI with explicit flags
            command = self._build_standard_command()
        else:
            # Environment-based CLI that reads COCODE_* variables directly
            command = self._build_env_based_command()

        logger.debug(f"Codex CLI command: {' '.join(command)}")
        return command

    def _validate_environment_variables(self) -> None:
        """Validate required environment variables."""
        issue_file = os.environ.get("COCODE_ISSUE_BODY_FILE")
        issue_number = os.environ.get("COCODE_ISSUE_NUMBER")

        # Validate issue file exists
        if issue_file and not Path(issue_file).exists():
            logger.warning(f"Issue file does not exist: {issue_file}")

        # Validate issue number is numeric
        if issue_number and not issue_number.isdigit():
            logger.warning(f"Issue number is not numeric: {issue_number}")

    def _build_standard_command(self) -> list[str]:
        """Build command for standard CLI interface with flags."""
        command: list[str] = [self.command_path]

        # Add subcommand
        command.append("fix")

        # Add issue file if available
        issue_file = os.environ.get("COCODE_ISSUE_BODY_FILE")
        if issue_file:
            command.extend(["--issue-file", issue_file])

        # Add issue number if available
        issue_number = os.environ.get("COCODE_ISSUE_NUMBER")
        if issue_number:
            command.extend(["--issue-number", issue_number])

        # Add non-interactive flag
        command.append("--no-interactive")

        # Add commit marker if available
        ready_marker = os.environ.get("COCODE_READY_MARKER")
        if ready_marker:
            command.extend(["--commit-marker", ready_marker])

        return command

    def _build_env_based_command(self) -> list[str]:
        """Build command for environment-based CLI that reads COCODE_* vars."""
        # Simple command that relies on environment variables
        return [self.command_path]

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
        output_lower = output.lower()

        # More granular authentication error detection
        if "authentication" in output_lower or "api key" in output_lower:
            # Try to determine which key is the issue
            if "codex_api_key" in output_lower:
                return f"{base_msg}: Authentication failed. CODEX_API_KEY is missing or invalid"
            elif "openai_api_key" in output_lower:
                return f"{base_msg}: Authentication failed. OPENAI_API_KEY is missing or invalid"
            elif "unauthorized" in output_lower or "401" in output:
                return f"{base_msg}: Authentication failed. API key is invalid or expired"
            else:
                return f"{base_msg}: Authentication failed. Check CODEX_API_KEY or OPENAI_API_KEY environment variables"

        # Rate limiting with more specific guidance
        elif "rate limit" in output_lower:
            if "quota" in output_lower:
                return f"{base_msg}: API quota exceeded. Check your plan limits or wait until quota resets"
            else:
                return f"{base_msg}: Rate limit exceeded. Please wait before retrying"

        # Network errors with more detail
        elif "network" in output_lower or "connection" in output_lower:
            if "timeout" in output_lower:
                return f"{base_msg}: Network timeout. The API server might be slow or unreachable"
            elif "refused" in output_lower:
                return f"{base_msg}: Connection refused. Check if you're behind a firewall or proxy"
            else:
                return f"{base_msg}: Network error. Check your internet connection"

        # Permission errors
        elif "permission" in output_lower:
            return f"{base_msg}: Permission denied. Check file permissions in worktree"

        # Model-related errors
        elif "model" in output_lower:
            if "not found" in output_lower or "invalid" in output_lower:
                return f"{base_msg}: Model not found. Check CODEX_MODEL environment variable"
            elif "deprecated" in output_lower:
                return f"{base_msg}: Model deprecated. Update CODEX_MODEL to a supported model"

        # Token limit errors
        elif "token" in output_lower and ("limit" in output_lower or "exceeded" in output_lower):
            return f"{base_msg}: Token limit exceeded. Try reducing CODEX_MAX_TOKENS or splitting the issue"

        return base_msg
