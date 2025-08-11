"""Test log streaming to TUI panels."""

from unittest.mock import Mock

import pytest

from cocode.agents.base import AgentStatus
from cocode.agents.lifecycle import AgentLifecycleManager, AgentState
from cocode.tui.app import CocodeApp


@pytest.mark.asyncio
async def test_log_streaming_to_panels():
    """Test that agent output is streamed to panels in real-time."""
    # Create a mock lifecycle manager
    mock_lifecycle_mgr = Mock(spec=AgentLifecycleManager)
    mock_lifecycle_mgr.agents = {"test-agent": Mock()}

    # Track callback registration
    stdout_callback = None
    stderr_callback = None
    completion_callback = None

    def mock_start_agent(name, issue_num, issue_body, issue_url, **kwargs):
        nonlocal stdout_callback, stderr_callback, completion_callback
        stdout_callback = kwargs.get("stdout_callback")
        stderr_callback = kwargs.get("stderr_callback")
        completion_callback = kwargs.get("completion_callback")
        return True

    mock_lifecycle_mgr.start_agent.side_effect = mock_start_agent
    mock_lifecycle_mgr.get_agent_info.return_value = Mock(state=AgentState.RUNNING)

    # Create app with mock lifecycle manager
    app = CocodeApp(
        lifecycle_manager=mock_lifecycle_mgr,
        issue_number=123,
        issue_body="Test issue body",
        issue_url="https://github.com/test/repo/issues/123",
        dry_run=False,
        update_interval=0.1,  # Fast updates for testing
    )

    async with app.run_test() as pilot:
        # Wait for app to start
        await pilot.pause()

        # Start agents (this should register callbacks)
        app.start_all_agents()

        # Verify callbacks were registered
        assert stdout_callback is not None, "stdout callback should be registered"
        assert stderr_callback is not None, "stderr callback should be registered"
        assert completion_callback is not None, "completion callback should be registered"

        # Simulate output from agent
        test_output = "Test output line from agent"
        error_output = "Error message from agent"

        # Call the callbacks as if agent was producing output
        stdout_callback(test_output)
        stderr_callback(error_output)

        # Let the UI update
        await pilot.pause()

        # Check that logs appear in the panel
        log_widget = app.query_one("#log-test-agent")
        assert log_widget is not None, "Log widget should exist"

        # Get the log content
        log_content = log_widget.lines

        # Verify output was added to logs
        # The panel adds timestamps, so we check for the content
        assert any(
            test_output in str(line) for line in log_content
        ), f"stdout output should be in logs. Got: {log_content}"
        assert any(
            error_output in str(line) for line in log_content
        ), f"stderr output should be in logs. Got: {log_content}"

        # Test completion callback
        status = AgentStatus(
            name="test-agent",
            branch="cocode/123-test-agent",
            worktree=Mock(),
            ready=True,
            exit_code=0,
        )
        completion_callback(status)

        await pilot.pause()

        # Check for completion message
        log_content = log_widget.lines
        assert any(
            "ready" in str(line).lower() for line in log_content
        ), "Ready message should be in logs"


@pytest.mark.asyncio
async def test_log_buffering_and_performance():
    """Test that log buffering handles high-volume output efficiently."""
    mock_lifecycle_mgr = Mock(spec=AgentLifecycleManager)
    mock_lifecycle_mgr.agents = {"fast-agent": Mock()}

    stdout_callback = None

    def mock_start_agent(name, issue_num, issue_body, issue_url, **kwargs):
        nonlocal stdout_callback
        stdout_callback = kwargs.get("stdout_callback")
        return True

    mock_lifecycle_mgr.start_agent.side_effect = mock_start_agent
    mock_lifecycle_mgr.get_agent_info.return_value = Mock(state=AgentState.RUNNING)

    app = CocodeApp(
        lifecycle_manager=mock_lifecycle_mgr,
        issue_number=456,
        issue_body="Test issue",
        issue_url="https://github.com/test/repo/issues/456",
    )

    async with app.run_test() as pilot:
        await pilot.pause()

        # Start agents
        app.start_all_agents()
        assert stdout_callback is not None

        # Simulate rapid output (1000 lines)
        for i in range(1000):
            stdout_callback(f"Line {i}: " + "x" * 100)

        # Let UI process
        await pilot.pause()

        # Check that log widget exists and has bounded content
        log_widget = app.query_one("#log-fast-agent")
        assert log_widget is not None

        # Verify max_lines is respected (should be MAX_LOG_LINES from AgentPanel)
        from cocode.tui.agent_panel import AgentPanel

        assert (
            len(log_widget.lines) <= AgentPanel.MAX_LOG_LINES
        ), f"Log should respect max lines limit. Got {len(log_widget.lines)} lines"

        # Verify recent lines are preserved (FIFO buffer)
        log_content = log_widget.lines
        if log_content:
            # Check that later lines are present (buffer should keep most recent)
            assert any(
                "Line 999" in str(line) for line in log_content[-10:]
            ), "Recent output should be preserved in buffer"


@pytest.mark.asyncio
async def test_multiple_agents_concurrent_streaming():
    """Test that multiple agents can stream logs concurrently."""
    mock_lifecycle_mgr = Mock(spec=AgentLifecycleManager)
    mock_lifecycle_mgr.agents = {
        "agent-1": Mock(),
        "agent-2": Mock(),
        "agent-3": Mock(),
    }

    callbacks = {}

    def mock_start_agent(name, issue_num, issue_body, issue_url, **kwargs):
        callbacks[name] = {
            "stdout": kwargs.get("stdout_callback"),
            "stderr": kwargs.get("stderr_callback"),
        }
        return True

    mock_lifecycle_mgr.start_agent.side_effect = mock_start_agent
    mock_lifecycle_mgr.get_agent_info.return_value = Mock(state=AgentState.RUNNING)

    app = CocodeApp(
        lifecycle_manager=mock_lifecycle_mgr,
        issue_number=789,
        issue_body="Test concurrent streaming",
        issue_url="https://github.com/test/repo/issues/789",
    )

    async with app.run_test() as pilot:
        await pilot.pause()

        # Start all agents
        app.start_all_agents()

        # Verify all agents have callbacks
        assert len(callbacks) == 3
        for agent_name in ["agent-1", "agent-2", "agent-3"]:
            assert callbacks[agent_name]["stdout"] is not None
            assert callbacks[agent_name]["stderr"] is not None

        # Simulate concurrent output from all agents
        for i in range(10):
            for agent_name in callbacks:
                callbacks[agent_name]["stdout"](f"{agent_name}: Processing step {i}")

        await pilot.pause()

        # Verify each agent's panel has its own logs
        for agent_name in ["agent-1", "agent-2", "agent-3"]:
            log_widget = app.query_one(f"#log-{agent_name}")
            assert log_widget is not None

            log_content = log_widget.lines
            # Each agent should have its own output
            assert any(
                f"{agent_name}: Processing" in str(line) for line in log_content
            ), f"{agent_name} should have its own log output"

            # Should not have other agents' output
            other_agents = [a for a in ["agent-1", "agent-2", "agent-3"] if a != agent_name]
            for other in other_agents:
                assert not any(
                    f"{other}: Processing" in str(line) for line in log_content
                ), f"{agent_name} should not have {other}'s output"
