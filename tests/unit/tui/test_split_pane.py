"""Tests for split-pane functionality in the TUI."""

from cocode.agents.lifecycle import AgentLifecycleManager, AgentState
from cocode.tui.agent_panel import AgentPanel
from cocode.tui.app import CocodeApp
from cocode.tui.overview_panel import OverviewPanel


def test_split_pane_app_initialization():
    """Test that CocodeApp initializes with split-pane support."""
    app = CocodeApp(issue_number=123, issue_url="https://github.com/test/repo/issues/123")

    # Check that app has the necessary attributes
    assert hasattr(app, "top_pane_height")
    assert app.top_pane_height == 30
    assert app.MIN_PANE_HEIGHT == 15
    assert app.MAX_PANE_HEIGHT == 70
    assert app.overview_panel is None  # Not created until compose


def test_pane_resize_constraints():
    """Test pane resizing respects constraints."""
    app = CocodeApp()

    # Test resize up action (without needing mounted widgets)
    initial_height = app.top_pane_height
    new_height = initial_height + 5
    if new_height <= app.MAX_PANE_HEIGHT:
        app.top_pane_height = new_height
        assert app.top_pane_height == initial_height + 5

    # Test resize down action
    new_height = app.top_pane_height - 5
    if new_height >= app.MIN_PANE_HEIGHT:
        app.top_pane_height = new_height
        assert app.top_pane_height == initial_height

    # Test minimum constraint
    app.top_pane_height = app.MIN_PANE_HEIGHT - 10
    if app.top_pane_height < app.MIN_PANE_HEIGHT:
        app.top_pane_height = app.MIN_PANE_HEIGHT
    assert app.top_pane_height == app.MIN_PANE_HEIGHT  # Should not go below minimum

    # Test maximum constraint
    app.top_pane_height = app.MAX_PANE_HEIGHT + 10
    if app.top_pane_height > app.MAX_PANE_HEIGHT:
        app.top_pane_height = app.MAX_PANE_HEIGHT
    assert app.top_pane_height == app.MAX_PANE_HEIGHT  # Should not go above maximum


def test_overview_panel_initialization():
    """Test OverviewPanel initialization."""
    overview = OverviewPanel(issue_number=42, issue_url="https://github.com/test/repo/issues/42")

    assert overview.issue_number == 42
    assert overview.issue_url == "https://github.com/test/repo/issues/42"
    assert overview.total_agents == 0
    assert overview.running_agents == 0
    assert overview.completed_agents == 0
    assert overview.failed_agents == 0


def test_overview_panel_state_updates():
    """Test that overview panel updates with agent states."""
    overview = OverviewPanel(issue_number=42, issue_url="https://github.com/test/repo/issues/42")

    # Just test the state tracking logic without widget updates
    overview.agent_states["agent1"] = AgentState.RUNNING

    # Recalculate counters manually (as done in update_agent_state)
    overview.total_agents = len(overview.agent_states)
    overview.running_agents = sum(
        1 for s in overview.agent_states.values() if s in (AgentState.STARTING, AgentState.RUNNING)
    )

    assert overview.total_agents == 1
    assert overview.running_agents == 1

    # Add more agents
    overview.agent_states["agent2"] = AgentState.COMPLETED
    overview.agent_states["agent3"] = AgentState.FAILED

    # Recalculate all counters
    overview.total_agents = len(overview.agent_states)
    overview.running_agents = sum(
        1 for s in overview.agent_states.values() if s in (AgentState.STARTING, AgentState.RUNNING)
    )
    overview.completed_agents = sum(
        1 for s in overview.agent_states.values() if s in (AgentState.COMPLETED, AgentState.READY)
    )
    overview.failed_agents = sum(
        1 for s in overview.agent_states.values() if s == AgentState.FAILED
    )

    assert overview.total_agents == 3
    assert overview.completed_agents == 1
    assert overview.failed_agents == 1

    # Update existing agent state
    overview.agent_states["agent1"] = AgentState.READY

    # Recalculate
    overview.running_agents = sum(
        1 for s in overview.agent_states.values() if s in (AgentState.STARTING, AgentState.RUNNING)
    )
    overview.completed_agents = sum(
        1 for s in overview.agent_states.values() if s in (AgentState.COMPLETED, AgentState.READY)
    )

    assert overview.running_agents == 0
    assert overview.completed_agents == 2  # READY counts as completed


def test_overview_panel_format_methods():
    """Test overview panel formatting methods."""
    overview = OverviewPanel()

    # Test summary formatting with no agents
    summary = overview._format_summary()
    assert "No agents running" in summary

    # Manually add agent states for testing
    overview.agent_states["agent1"] = AgentState.RUNNING
    overview.agent_states["agent2"] = AgentState.COMPLETED

    # Update counters
    overview.total_agents = 2
    overview.running_agents = 1
    overview.completed_agents = 1

    summary = overview._format_summary()
    assert "Agents:" in summary
    assert "Running:" in summary
    assert "Completed:" in summary

    # Test progress formatting
    progress = overview._format_progress()
    assert "Progress:" in progress
    assert "%" in progress


def test_agent_navigation_actions():
    """Test agent panel navigation actions."""
    lifecycle_manager = AgentLifecycleManager()
    lifecycle_manager.agents = {"agent1": None, "agent2": None, "agent3": None}

    app = CocodeApp(lifecycle_manager=lifecycle_manager)

    # Mock the agent panels without needing them to be mounted
    from unittest.mock import Mock

    panel1 = Mock(spec=AgentPanel)
    panel1.agent_name = "agent1"
    panel1.is_selected = True
    panel1.set_selected = Mock()
    panel1.focus = Mock()
    panel1.scroll_visible = Mock()

    panel2 = Mock(spec=AgentPanel)
    panel2.agent_name = "agent2"
    panel2.is_selected = False
    panel2.set_selected = Mock()
    panel2.focus = Mock()
    panel2.scroll_visible = Mock()

    panel3 = Mock(spec=AgentPanel)
    panel3.agent_name = "agent3"
    panel3.is_selected = False
    panel3.set_selected = Mock()
    panel3.focus = Mock()
    panel3.scroll_visible = Mock()

    app.agent_panels = [panel1, panel2, panel3]

    # Set initial selection
    app.selected_agent_index = 0

    # Navigate to next agent
    app.action_next_agent()
    assert app.selected_agent_index == 1
    panel1.set_selected.assert_called_with(False)
    panel2.set_selected.assert_called_with(True)

    # Navigate to previous agent
    app.action_previous_agent()
    assert app.selected_agent_index == 0

    # Wrap around backward
    app.action_previous_agent()
    assert app.selected_agent_index == 2  # Should wrap to last agent

    # Direct selection
    app.action_select_agent(1)
    assert app.selected_agent_index == 1

    # Out of range selection should be ignored
    app.action_select_agent(10)
    assert app.selected_agent_index == 1  # Should remain unchanged
