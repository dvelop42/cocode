#!/usr/bin/env python3
"""Demo script to showcase log streaming functionality in cocode TUI.

This script demonstrates how agent output is streamed in real-time to the TUI panels.
It simulates agent execution with various types of output.
"""

import sys
import time
from pathlib import Path
from unittest.mock import Mock

# Add parent directory to path to import cocode modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cocode.agents.lifecycle import AgentLifecycleManager, AgentState
from cocode.tui.app import CocodeApp


class DemoLifecycleManager(AgentLifecycleManager):
    """Mock lifecycle manager that simulates agent output."""

    def __init__(self):
        super().__init__()
        # Register demo agents
        self.agents = {
            "fast-agent": Mock(),
            "slow-agent": Mock(),
            "error-agent": Mock(),
        }
        self._demo_callbacks = {}

    def start_agent(
        self,
        agent_name,
        issue_number,
        issue_body,
        issue_url,
        stdout_callback=None,
        stderr_callback=None,
        completion_callback=None,
    ):
        """Start a demo agent that produces simulated output."""
        self._demo_callbacks[agent_name] = {
            "stdout": stdout_callback,
            "stderr": stderr_callback,
            "completion": completion_callback,
        }

        # Start async task to simulate agent output
        import threading

        thread = threading.Thread(target=self._simulate_agent, args=(agent_name,), daemon=True)
        thread.start()
        return True

    def _simulate_agent(self, agent_name):
        """Simulate agent execution with various output patterns."""
        callbacks = self._demo_callbacks.get(agent_name, {})
        stdout_cb = callbacks.get("stdout")
        stderr_cb = callbacks.get("stderr")
        completion_cb = callbacks.get("completion")

        if agent_name == "fast-agent":
            # Fast agent - rapid output
            if stdout_cb:
                stdout_cb("🚀 Fast agent starting...")
                for i in range(20):
                    time.sleep(0.1)
                    stdout_cb(f"Processing item {i+1}/20...")
                stdout_cb("✅ Fast agent completed successfully!")

            if completion_cb:
                from cocode.agents.base import AgentStatus

                status = AgentStatus(
                    name=agent_name,
                    branch=f"cocode/demo-{agent_name}",
                    worktree=Path("/tmp"),
                    ready=True,
                    exit_code=0,
                )
                completion_cb(status)

        elif agent_name == "slow-agent":
            # Slow agent - gradual output with progress
            if stdout_cb:
                stdout_cb("🐌 Slow agent starting...")
                stdout_cb("Analyzing codebase...")
                time.sleep(1)

                for i in range(5):
                    time.sleep(1)
                    stdout_cb(f"Step {i+1}/5: {'█' * (i+1)}{'░' * (5-i-1)}")
                    stdout_cb(f"  - Found {(i+1)*10} files")
                    stdout_cb(f"  - Processed {(i+1)*100} lines")

                stdout_cb("✅ Slow agent completed!")

            if completion_cb:
                from cocode.agents.base import AgentStatus

                status = AgentStatus(
                    name=agent_name,
                    branch=f"cocode/demo-{agent_name}",
                    worktree=Path("/tmp"),
                    ready=True,
                    exit_code=0,
                )
                completion_cb(status)

        elif agent_name == "error-agent":
            # Error agent - mix of stdout and stderr
            if stdout_cb:
                stdout_cb("⚠️ Error-prone agent starting...")
                stdout_cb("Attempting risky operation...")

            time.sleep(0.5)

            if stderr_cb:
                stderr_cb("WARNING: Configuration file not found")
                stderr_cb("WARNING: Using default settings")

            time.sleep(0.5)

            if stdout_cb:
                stdout_cb("Trying to recover...")

            time.sleep(0.5)

            if stderr_cb:
                stderr_cb("ERROR: Unable to complete operation")
                stderr_cb("ERROR: Fatal error encountered")

            if completion_cb:
                from cocode.agents.base import AgentStatus

                status = AgentStatus(
                    name=agent_name,
                    branch=f"cocode/demo-{agent_name}",
                    worktree=Path("/tmp"),
                    ready=False,
                    exit_code=1,
                    error_message="Simulated error for demo",
                )
                completion_cb(status)

    def get_agent_info(self, agent_name):
        """Return mock agent info."""
        return Mock(state=AgentState.RUNNING)

    def shutdown_all(self):
        """Clean shutdown."""
        pass


def main():
    """Run the log streaming demo."""
    print("🎬 Log Streaming Demo for Cocode TUI")
    print("=" * 50)
    print("\nThis demo shows how agent output is streamed")
    print("in real-time to the TUI panels.\n")
    print("Features demonstrated:")
    print("  • Real-time output streaming")
    print("  • Multiple concurrent agents")
    print("  • Stdout and stderr handling")
    print("  • Progress indicators")
    print("  • Error messages")
    print("\nPress 'q' to quit the demo\n")
    print("Starting TUI in 3 seconds...")
    time.sleep(3)

    # Create demo app
    demo_manager = DemoLifecycleManager()
    app = CocodeApp(
        lifecycle_manager=demo_manager,
        issue_number=999,
        issue_body="Demo issue to showcase log streaming",
        issue_url="https://github.com/demo/repo/issues/999",
        dry_run=False,
        update_interval=0.5,
    )

    # Start agents after TUI loads
    app.call_after_refresh(app.start_all_agents)

    # Run the TUI
    app.run()

    print("\n✨ Demo completed!")
    print("The log streaming functionality allows cocode to:")
    print("  • Show real-time feedback from agents")
    print("  • Monitor multiple agents simultaneously")
    print("  • Track progress and errors as they happen")
    print("  • Maintain a scrollable log history")


if __name__ == "__main__":
    main()
