"""Agent runner with integrated temp file management.

This module demonstrates how the TempFileManager integrates with agent execution
to handle issue body temp files and cleanup.
"""

import logging
import subprocess
from pathlib import Path

from cocode.agents.base import Agent, AgentStatus
from cocode.utils.exit_codes import ExitCode
from cocode.utils.tempfile_manager import get_temp_manager

logger = logging.getLogger(__name__)


class AgentRunner:
    """Runs agents with proper temp file management."""

    def __init__(self) -> None:
        """Initialize the agent runner."""
        self.temp_manager = get_temp_manager()

    def run_agent(
        self,
        agent: Agent,
        worktree_path: Path,
        issue_number: int,
        issue_body: str,
        issue_url: str,
        timeout: int = 900,
    ) -> AgentStatus:
        """Run an agent with proper environment setup and cleanup.

        Args:
            agent: The agent to run
            worktree_path: Path to the git worktree
            issue_number: GitHub issue number
            issue_body: Issue body content
            issue_url: URL to the GitHub issue
            timeout: Timeout in seconds (default: 15 minutes)

        Returns:
            AgentStatus with execution results
        """
        # Create temp file for issue body
        issue_body_file = self.temp_manager.write_issue_body(issue_number, issue_body)

        try:
            # Prepare environment with temp file path
            env = self._prepare_safe_environment(
                worktree_path=worktree_path,
                issue_number=issue_number,
                issue_url=issue_url,
                issue_body_file=issue_body_file,
            )

            # Get agent command
            command = agent.get_command()

            logger.info(f"Running agent {agent.name} for issue #{issue_number}")
            logger.debug(f"Command: {command}")
            logger.debug(f"Issue body temp file: {issue_body_file}")

            # Run the agent
            try:
                result = subprocess.run(
                    command,
                    cwd=worktree_path,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=timeout,
                )

                # Check if agent is ready
                ready = agent.check_ready(worktree_path)

                return AgentStatus(
                    name=agent.name,
                    branch=f"cocode/{issue_number}-{agent.name}",
                    worktree=worktree_path,
                    ready=ready,
                    exit_code=result.returncode,
                    error_message=None if result.returncode == 0 else result.stdout,
                )

            except subprocess.TimeoutExpired:
                logger.error(f"Agent {agent.name} timed out after {timeout} seconds")
                return AgentStatus(
                    name=agent.name,
                    branch=f"cocode/{issue_number}-{agent.name}",
                    worktree=worktree_path,
                    ready=False,
                    exit_code=ExitCode.TIMEOUT,
                    error_message=f"Agent execution exceeded {timeout} second timeout",
                )

        finally:
            # Cleanup temp file (optional - will be cleaned on exit anyway)
            self.temp_manager.cleanup_file(issue_body_file)

    def _prepare_safe_environment(
        self, worktree_path: Path, issue_number: int, issue_url: str, issue_body_file: Path
    ) -> dict[str, str]:
        """Prepare safe environment variables for agent execution.

        Following ADR-004 security model with allowlist-based filtering.
        """
        import os

        # Allowed environment variables (from ADR-004)
        ALLOWED_ENV_VARS = {
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

        # Safe PATH directories
        SAFE_PATH_DIRS = ["/usr/bin", "/bin", "/usr/local/bin", "/opt/homebrew/bin"]
        safe_path = ":".join(SAFE_PATH_DIRS)

        # Filter existing environment
        filtered_env = {
            k: v for k, v in os.environ.items() if k in ALLOWED_ENV_VARS or k.startswith("COCODE_")
        }

        # Add cocode-specific variables
        cocode_env = {
            "COCODE_REPO_PATH": str(worktree_path),
            "COCODE_ISSUE_NUMBER": str(issue_number),
            "COCODE_ISSUE_URL": issue_url,
            "COCODE_ISSUE_BODY_FILE": str(issue_body_file),
            "COCODE_READY_MARKER": "cocode ready for check",
            "PATH": safe_path,
        }

        return {**filtered_env, **cocode_env}

    def cleanup(self) -> None:
        """Clean up all temporary files.

        This is called automatically on exit but can be called manually
        to free resources early.
        """
        self.temp_manager.cleanup_all()
