"""Agent runner with integrated temp file management.

This module demonstrates how the TempFileManager integrates with agent execution
to handle issue body temp files and cleanup.
"""

import logging
import subprocess
from collections.abc import Callable
from pathlib import Path

from cocode.agents.base import Agent, AgentStatus
from cocode.utils.exit_codes import ExitCode
from cocode.utils.subprocess import StreamingSubprocess
from cocode.utils.tempfile_manager import get_temp_manager

logger = logging.getLogger(__name__)


class AgentRunner:
    """Runs agents with proper temp file management."""

    def __init__(self) -> None:
        """Initialize the agent runner.

        Uses the global TempFileManager singleton for consistent
        temp file management across the application.
        """
        self.temp_manager = get_temp_manager()

    def run_agent(
        self,
        agent: Agent,
        worktree_path: Path,
        issue_number: int,
        issue_body: str,
        issue_url: str,
        timeout: int = 900,
        stdout_callback: Callable[[str], None] | None = None,
        stderr_callback: Callable[[str], None] | None = None,
    ) -> AgentStatus:
        """Run an agent with proper environment setup and cleanup.

        Args:
            agent: The agent to run
            worktree_path: Path to the git worktree
            issue_number: GitHub issue number
            issue_body: Issue body content
            issue_url: URL to the GitHub issue
            timeout: Timeout in seconds (default: 15 minutes)
            stdout_callback: Optional callback for stdout lines
            stderr_callback: Optional callback for stderr lines

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

            # Collect output for error messages
            output_lines = []

            def collect_output(line: str) -> None:
                output_lines.append(line)
                if stdout_callback:
                    stdout_callback(line)

            def handle_stderr(line: str) -> None:
                output_lines.append(f"[stderr] {line}")
                if stderr_callback:
                    stderr_callback(line)

            # Run the agent with streaming
            streaming_proc = StreamingSubprocess(
                command=command,
                cwd=worktree_path,
                env=env,
                timeout=timeout,
            )

            try:
                exit_code = streaming_proc.run(
                    stdout_callback=collect_output,
                    stderr_callback=handle_stderr,
                )

                # Check if agent is ready
                ready = agent.check_ready(worktree_path)

                return AgentStatus(
                    name=agent.name,
                    branch=f"cocode/{issue_number}-{agent.name}",
                    worktree=worktree_path,
                    ready=ready,
                    exit_code=exit_code,
                    error_message=None if exit_code == 0 else "\n".join(output_lines),
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
            except KeyboardInterrupt as e:
                logger.info(f"Agent {agent.name} was cancelled")
                return AgentStatus(
                    name=agent.name,
                    branch=f"cocode/{issue_number}-{agent.name}",
                    worktree=worktree_path,
                    ready=False,
                    exit_code=ExitCode.INTERRUPTED,
                    error_message=str(e),
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

        # Allowlist prefixes for agent auth and config vars (minimal, explicit)
        AGENT_ENV_PREFIXES = (
            "CLAUDE_",
            "ANTHROPIC_",
            "CODEX_",
            "OPENAI_",
        )

        # Filter existing environment
        filtered_env = {
            k: v
            for k, v in os.environ.items()
            if k in ALLOWED_ENV_VARS or k.startswith("COCODE_") or k.startswith(AGENT_ENV_PREFIXES)
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
