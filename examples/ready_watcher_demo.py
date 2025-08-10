#!/usr/bin/env python3
"""Demo script showing ready marker watcher in action.

This demonstrates how the ready marker watcher monitors git commits
and detects when an agent has signaled completion.
"""

import subprocess
import tempfile
import time
from pathlib import Path
from threading import Thread

from cocode.agents.ready_watcher import ReadyMarkerWatcher


def simulate_agent_work(repo_path: Path) -> None:
    """Simulate an agent making commits over time."""
    print(f"🤖 Agent starting work in {repo_path}")
    time.sleep(2)

    # First commit (not ready)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "feat: working on issue"],
        cwd=repo_path,
        capture_output=True,
    )
    print("🤖 Agent made first commit (not ready)")

    time.sleep(3)

    # Second commit (not ready)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "fix: addressing edge case"],
        cwd=repo_path,
        capture_output=True,
    )
    print("🤖 Agent made second commit (not ready)")

    time.sleep(4)

    # Final commit with ready marker
    subprocess.run(
        [
            "git",
            "commit",
            "--allow-empty",
            "-m",
            "fix: completed issue #123\n\ncocode ready for check",
        ],
        cwd=repo_path,
        capture_output=True,
    )
    print("🤖 Agent made final commit with ready marker")


def main():
    """Run the demo."""
    print("Ready Marker Watcher Demo")
    print("=" * 40)

    # Create temporary git repository
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo_path,
            capture_output=True,
        )

        # Initial commit
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "Initial commit"],
            cwd=repo_path,
            capture_output=True,
        )

        print(f"📁 Created test repository at: {repo_path}")
        print()

        # Start agent simulation in background
        agent_thread = Thread(target=simulate_agent_work, args=(repo_path,))
        agent_thread.start()

        # Create watcher with custom settings for demo
        watcher = ReadyMarkerWatcher(
            worktree_path=repo_path,
            ready_marker="cocode ready for check",
            initial_delay=0.5,
            max_delay=3.0,
            backoff_factor=1.5,
        )

        print("👀 Starting ready marker watch...")
        print("   (watching for 'cocode ready for check' in commits)")
        print()

        def on_new_commit(is_ready: bool):
            """Callback when new commit detected."""
            if is_ready:
                print("✅ Ready marker detected!")
            else:
                print("📝 New commit detected (not ready yet)")

        def on_check_interval(delay: float):
            """Callback before each check."""
            print(f"⏰ Checking for new commits... (next check in {delay:.1f}s)")

        # Watch for ready marker
        start_time = time.time()
        is_ready = watcher.watch(
            timeout=30,
            callback=on_new_commit,
            check_interval_callback=on_check_interval,
        )

        elapsed = time.time() - start_time

        print()
        if is_ready:
            print(f"🎉 Agent completed successfully after {elapsed:.1f} seconds!")

            # Show the commit with ready marker
            result = subprocess.run(
                ["git", "log", "-1", "--format=%B"],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )
            print("\nFinal commit message:")
            print("-" * 40)
            print(result.stdout)
        else:
            print(f"⏱️  Timeout reached after {elapsed:.1f} seconds")

        # Wait for agent thread to complete
        agent_thread.join()

    print("\nDemo complete!")


if __name__ == "__main__":
    main()
