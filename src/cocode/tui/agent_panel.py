"""Agent panel widget for the TUI."""

from datetime import datetime
from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import Log, Static

from cocode.agents.lifecycle import AgentState


class AgentPanel(Static):
    """Panel for displaying agent status and logs."""

    can_focus = True
    state = reactive(AgentState.IDLE)
    last_update = reactive(datetime.now())

    def __init__(
        self,
        agent_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize the agent panel.

        Args:
            agent_name: Name of the agent
        """
        super().__init__(*args, **kwargs)
        self.agent_name = agent_name
        self.border_title = f" {agent_name} "
        self.is_selected = False

    def compose(self) -> ComposeResult:
        """Compose the panel layout."""
        with Vertical():
            yield Static(self._format_title(), id=f"title-{self.agent_name}")
            yield Static(self._format_state(), id=f"status-{self.agent_name}")
            yield Log(id=f"log-{self.agent_name}", auto_scroll=True, max_lines=500)

    def _format_title(self) -> str:
        """Format the title with selection indicator."""
        if self.is_selected:
            return f"[bold bright_yellow]▶ {self.agent_name} ◀[/bold bright_yellow]"
        else:
            return f"[bold]{self.agent_name}[/bold]"

    def _format_state(self) -> str:
        """Format the current state for display."""
        state_icons = {
            AgentState.IDLE: ("⏸", "dim"),
            AgentState.STARTING: ("⟳", "yellow"),
            AgentState.RUNNING: ("▶", "blue"),
            AgentState.STOPPING: ("⏹", "yellow"),
            AgentState.STOPPED: ("⏹", "red"),
            AgentState.COMPLETED: ("✓", "green"),
            AgentState.FAILED: ("✗", "red"),
            AgentState.READY: ("✓", "bright_green"),
        }

        icon, color = state_icons.get(self.state, ("?", "white"))
        time_str = self.last_update.strftime("%H:%M:%S")

        return f"[{color}]{icon} {self.state.value}[/{color}] [dim]({time_str})[/dim]"

    def update_state(self, state: AgentState) -> None:
        """Update the agent's state.

        Args:
            state: New state for the agent
        """
        self.state = state
        self.last_update = datetime.now()
        status_widget = self.query_one(f"#status-{self.agent_name}", Static)
        status_widget.update(self._format_state())

    def add_log_line(self, line: str) -> None:
        """Add a line to the agent's log.

        Args:
            line: Log line to add
        """
        log_widget = self.query_one(f"#log-{self.agent_name}", Log)
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_widget.write_line(f"[dim]{timestamp}[/dim] {line}")

    def clear_logs(self) -> None:
        """Clear the agent's logs."""
        log_widget = self.query_one(f"#log-{self.agent_name}", Log)
        log_widget.clear()

    def set_selected(self, selected: bool) -> None:
        """Set whether this panel is selected.

        Args:
            selected: Whether the panel is selected
        """
        self.is_selected = selected
        if selected:
            self.add_class("selected")
            self.border_subtitle = " [SELECTED] "
        else:
            self.remove_class("selected")
            self.border_subtitle = ""

        # Update the title to show selection status
        title_widget = self.query_one(f"#title-{self.agent_name}", Static)
        title_widget.update(self._format_title())
