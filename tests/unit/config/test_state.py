"""Tests for state management."""

import json
from pathlib import Path

import pytest

from cocode.config.state import AgentState, RunState, StateError, StateManager


@pytest.fixture
def temp_state_file(tmp_path):
    """Create a temporary state file path."""
    return tmp_path / ".cocode" / "state.json"


@pytest.fixture
def state_manager(temp_state_file):
    """Create a StateManager with temp file."""
    return StateManager(state_path=temp_state_file)


class TestStateManager:
    """Test StateManager functionality."""

    def test_init_default_path(self):
        """Test initialization with default path."""
        manager = StateManager()
        assert manager.state_path == Path(".cocode/state.json")
        assert manager._current_run is None

    def test_init_custom_path(self, temp_state_file):
        """Test initialization with custom path."""
        manager = StateManager(state_path=temp_state_file)
        assert manager.state_path == temp_state_file

    def test_start_run(self, state_manager):
        """Test starting a new run."""
        run = state_manager.start_run(
            issue_number=123,
            issue_url="https://github.com/org/repo/issues/123",
            base_branch="main",
        )

        assert run.issue_number == 123
        assert run.issue_url == "https://github.com/org/repo/issues/123"
        assert run.base_branch == "main"
        assert run.started_at is not None
        assert run.completed_at is None
        assert len(run.agents) == 0

        # Verify persistence
        assert state_manager.state_path.exists()

    def test_start_run_with_active_run(self, state_manager):
        """Test starting run when one is already active."""
        state_manager.start_run(123, "url", "main")

        with pytest.raises(StateError, match="already an active run"):
            state_manager.start_run(456, "url2", "main")

    def test_add_agent(self, state_manager):
        """Test adding agents to a run."""
        state_manager.start_run(123, "url", "main")

        agent = state_manager.add_agent(
            name="claude-code",
            branch="cocode/123-claude-code",
            worktree="/tmp/cocode_claude-code",
        )

        assert agent.name == "claude-code"
        assert agent.branch == "cocode/123-claude-code"
        assert agent.worktree == "/tmp/cocode_claude-code"
        assert agent.status == "pending"
        assert agent.started_at is None

        # Verify agent is in run
        run = state_manager.get_current_run()
        assert len(run.agents) == 1
        assert run.agents[0] == agent

    def test_add_duplicate_agent(self, state_manager):
        """Test adding duplicate agent names."""
        state_manager.start_run(123, "url", "main")
        state_manager.add_agent("agent1", "branch1", "worktree1")

        with pytest.raises(StateError, match="already exists"):
            state_manager.add_agent("agent1", "branch2", "worktree2")

    def test_add_agent_no_run(self, state_manager):
        """Test adding agent without active run."""
        with pytest.raises(StateError, match="No active run"):
            state_manager.add_agent("agent", "branch", "worktree")

    def test_update_agent_status(self, state_manager):
        """Test updating agent status."""
        state_manager.start_run(123, "url", "main")
        state_manager.add_agent("agent1", "branch1", "worktree1")

        # Update to running
        state_manager.update_agent("agent1", status="running")
        agent = state_manager.get_agent("agent1")
        assert agent.status == "running"
        assert agent.started_at is not None

        # Update to ready
        state_manager.update_agent(
            "agent1",
            status="ready",
            exit_code=0,
            last_commit="abc123",
        )
        agent = state_manager.get_agent("agent1")
        assert agent.status == "ready"
        assert agent.exit_code == 0
        assert agent.last_commit == "abc123"
        assert agent.completed_at is not None

    def test_update_agent_failure(self, state_manager):
        """Test updating agent with failure."""
        state_manager.start_run(123, "url", "main")
        state_manager.add_agent("agent1", "branch1", "worktree1")

        state_manager.update_agent(
            "agent1",
            status="failed",
            exit_code=1,
            error_message="Command failed",
        )

        agent = state_manager.get_agent("agent1")
        assert agent.status == "failed"
        assert agent.exit_code == 1
        assert agent.error_message == "Command failed"
        assert agent.completed_at is not None

    def test_update_nonexistent_agent(self, state_manager):
        """Test updating agent that doesn't exist."""
        state_manager.start_run(123, "url", "main")

        with pytest.raises(StateError, match="not found"):
            state_manager.update_agent("nonexistent", status="ready")

    def test_get_agent(self, state_manager):
        """Test getting agent by name."""
        state_manager.start_run(123, "url", "main")
        agent1 = state_manager.add_agent("agent1", "branch1", "worktree1")
        agent2 = state_manager.add_agent("agent2", "branch2", "worktree2")

        assert state_manager.get_agent("agent1") == agent1
        assert state_manager.get_agent("agent2") == agent2
        assert state_manager.get_agent("nonexistent") is None

    def test_complete_run(self, state_manager):
        """Test completing a run."""
        state_manager.start_run(123, "url", "main")
        state_manager.add_agent("agent1", "branch1", "worktree1")

        state_manager.complete_run(
            selected_agent="agent1",
            pr_url="https://github.com/org/repo/pull/456",
        )

        run = state_manager.get_current_run()
        assert run.completed_at is not None
        assert run.selected_agent == "agent1"
        assert run.pr_url == "https://github.com/org/repo/pull/456"

    def test_complete_run_no_active(self, state_manager):
        """Test completing when no active run."""
        with pytest.raises(StateError, match="No active run"):
            state_manager.complete_run()

    def test_abort_run(self, state_manager):
        """Test aborting a run."""
        state_manager.start_run(123, "url", "main")
        state_manager.add_agent("agent1", "branch1", "worktree1")
        state_manager.add_agent("agent2", "branch2", "worktree2")
        state_manager.update_agent("agent1", status="running")

        state_manager.abort_run()

        run = state_manager.get_current_run()
        assert run.completed_at is not None

        # All agents should be cancelled
        agent1 = state_manager.get_agent("agent1")
        agent2 = state_manager.get_agent("agent2")
        assert agent1.status == "cancelled"
        assert agent2.status == "cancelled"
        assert agent1.completed_at is not None
        assert agent2.completed_at is not None

    def test_abort_run_no_active(self, state_manager):
        """Test aborting when no active run."""
        with pytest.raises(StateError, match="No active run"):
            state_manager.abort_run()

    def test_load_state(self, state_manager, temp_state_file):
        """Test loading state from disk."""
        # Create a run and persist it
        state_manager.start_run(123, "url", "main")
        state_manager.add_agent("agent1", "branch1", "worktree1")
        state_manager.update_agent("agent1", status="ready")

        # Create new manager and load
        new_manager = StateManager(state_path=temp_state_file)
        loaded_run = new_manager.load()

        assert loaded_run is not None
        assert loaded_run.issue_number == 123
        assert len(loaded_run.agents) == 1
        assert loaded_run.agents[0].name == "agent1"
        assert loaded_run.agents[0].status == "ready"

    def test_load_no_state_file(self, state_manager):
        """Test loading when no state file exists."""
        result = state_manager.load()
        assert result is None

    def test_load_corrupted_state(self, state_manager, temp_state_file):
        """Test loading corrupted state file."""
        temp_state_file.parent.mkdir(parents=True, exist_ok=True)
        temp_state_file.write_text("invalid json")

        with pytest.raises(StateError, match="Corrupted state file"):
            state_manager.load()

    def test_clear_state(self, state_manager):
        """Test clearing state."""
        state_manager.start_run(123, "url", "main")
        assert state_manager.state_path.exists()

        state_manager.clear()
        assert state_manager._current_run is None
        assert not state_manager.state_path.exists()

    def test_can_recover(self, state_manager):
        """Test checking if recovery is possible."""
        # No state file
        assert not state_manager.can_recover()

        # Active run
        state_manager.start_run(123, "url", "main")
        new_manager = StateManager(state_path=state_manager.state_path)
        assert new_manager.can_recover()

        # Completed run
        state_manager.complete_run()
        new_manager = StateManager(state_path=state_manager.state_path)
        assert not new_manager.can_recover()

    def test_recover(self, state_manager):
        """Test recovering from persisted state."""
        # Create incomplete run
        state_manager.start_run(123, "url", "main")
        state_manager.add_agent("agent1", "branch1", "worktree1")

        # Attempt recovery with new manager
        new_manager = StateManager(state_path=state_manager.state_path)
        recovered = new_manager.recover()

        assert recovered is not None
        assert recovered.issue_number == 123
        assert len(recovered.agents) == 1

    def test_recover_completed_run(self, state_manager):
        """Test recovering a completed run clears state."""
        state_manager.start_run(123, "url", "main")
        state_manager.complete_run()

        new_manager = StateManager(state_path=state_manager.state_path)
        recovered = new_manager.recover()

        assert recovered is None
        assert not new_manager.state_path.exists()

    def test_get_summary(self, state_manager):
        """Test getting run summary."""
        # No active run
        summary = state_manager.get_summary()
        assert summary["status"] == "no_active_run"

        # Active run with agents
        state_manager.start_run(123, "url", "main")
        state_manager.add_agent("agent1", "branch1", "worktree1")
        state_manager.add_agent("agent2", "branch2", "worktree2")
        state_manager.update_agent("agent1", status="ready")
        state_manager.update_agent("agent2", status="failed", exit_code=1)

        summary = state_manager.get_summary()
        assert summary["status"] == "active"
        assert summary["issue_number"] == 123
        assert summary["total_agents"] == 2
        assert summary["ready_agents"] == 1
        assert summary["failed_agents"] == 1
        assert summary["running_agents"] == 0
        assert summary["pending_agents"] == 0

        # Completed run
        state_manager.complete_run(selected_agent="agent1")
        summary = state_manager.get_summary()
        assert summary["status"] == "completed"
        assert summary["selected_agent"] == "agent1"

    def test_persistence_format(self, state_manager, temp_state_file):
        """Test the persisted JSON format."""
        state_manager.start_run(
            issue_number=123,
            issue_url="https://github.com/org/repo/issues/123",
            base_branch="develop",
        )
        state_manager.add_agent(
            name="test-agent",
            branch="cocode/123-test",
            worktree="/tmp/test",
        )
        state_manager.update_agent(
            "test-agent",
            status="ready",
            exit_code=0,
            last_commit="abc123",
        )

        # Read persisted file
        with open(temp_state_file) as f:
            data = json.load(f)

        assert "version" in data
        assert "run" in data

        run_data = data["run"]
        assert run_data["issue_number"] == 123
        assert run_data["issue_url"] == "https://github.com/org/repo/issues/123"
        assert run_data["base_branch"] == "develop"
        assert len(run_data["agents"]) == 1

        agent_data = run_data["agents"][0]
        assert agent_data["name"] == "test-agent"
        assert agent_data["status"] == "ready"
        assert agent_data["exit_code"] == 0
        assert agent_data["last_commit"] == "abc123"


class TestAgentState:
    """Test AgentState dataclass."""

    def test_agent_state_creation(self):
        """Test creating AgentState."""
        agent = AgentState(
            name="test",
            branch="test-branch",
            worktree="/tmp/test",
            status="pending",
        )

        assert agent.name == "test"
        assert agent.branch == "test-branch"
        assert agent.worktree == "/tmp/test"
        assert agent.status == "pending"
        assert agent.started_at is None
        assert agent.completed_at is None
        assert agent.exit_code is None


class TestRunState:
    """Test RunState dataclass."""

    def test_run_state_creation(self):
        """Test creating RunState."""
        run = RunState(
            issue_number=123,
            issue_url="https://github.com/org/repo/issues/123",
            base_branch="main",
        )

        assert run.issue_number == 123
        assert run.issue_url == "https://github.com/org/repo/issues/123"
        assert run.base_branch == "main"
        assert len(run.agents) == 0
        assert run.started_at is not None
        assert run.completed_at is None
        assert run.selected_agent is None
        assert run.pr_url is None
