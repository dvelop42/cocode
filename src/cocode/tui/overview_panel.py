"""Overview panel widget for displaying issue and agent summary."""

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.widgets import Label, Log, Static

from cocode.agents.lifecycle import AgentState


class OverviewPanel(Static):
    """Panel for displaying issue overview and agent summary."""

    can_focus = True
    total_agents = reactive(0)
    running_agents = reactive(0)
    completed_agents = reactive(0)
    failed_agents = reactive(0)

    def __init__(
        self,
        issue_number: int = 0,
        issue_url: str = "",
        issue_body: str = "",
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize the overview panel.

        Args:
            issue_number: GitHub issue number
            issue_url: URL to the GitHub issue
            issue_body: The content of the issue
        """
        super().__init__(*args, **kwargs)
        self.issue_number = issue_number
        self.issue_url = issue_url
        self.issue_body = issue_body
        self.border_title = " Overview "
        self.agent_states: dict[str, AgentState] = {}

    def compose(self) -> ComposeResult:
        """Compose the panel layout."""
        with VerticalScroll():
            # Issue header
            with Horizontal(classes="issue-header"):
                if self.issue_number:
                    yield Label(f"[bold]Issue #{self.issue_number}[/bold]", id="issue-number")
                else:
                    yield Label("No issue selected", id="no-issue")

            # Issue URL if available
            if self.issue_url:
                yield Label(f"[link]{self.issue_url}[/link]", id="issue-url", classes="issue-url")

            # Separator
            yield Static("─" * 40, classes="separator")

            # Issue content
            if self.issue_body:
                yield Static("[bold]Issue Description:[/bold]", classes="section-header")
                # Use Log widget for scrollable content
                log = Log(id="issue-content", auto_scroll=False, max_lines=1000)
                yield log

            # Agent summary section
            yield Static("─" * 40, classes="separator")
            yield Static("[bold]Agent Status:[/bold]", classes="section-header")
            yield Static(self._format_summary(), id="summary")
            yield Static(self._format_progress(), id="progress")

    def _format_summary(self) -> str:
        """Format the agent summary statistics."""
        parts = []

        if self.total_agents > 0:
            parts.append(f"[bold]Agents:[/bold] {self.total_agents}")

            if self.running_agents > 0:
                parts.append(f"[blue]Running:[/blue] {self.running_agents}")

            if self.completed_agents > 0:
                parts.append(f"[green]Completed:[/green] {self.completed_agents}")

            if self.failed_agents > 0:
                parts.append(f"[red]Failed:[/red] {self.failed_agents}")
        else:
            parts.append("No agents running")

        return " | ".join(parts) if parts else ""

    def _format_progress(self) -> str:
        """Format a progress indicator for agents."""
        if self.total_agents == 0:
            return ""

        # Create a simple text-based progress bar
        progress_pct = (self.completed_agents + self.failed_agents) / self.total_agents
        bar_width = 40

        # Build progress bar with different colors for status
        bar_parts = []

        # Calculate widths with floating point for better accuracy
        completed_ratio = self.completed_agents / self.total_agents
        failed_ratio = self.failed_agents / self.total_agents
        running_ratio = self.running_agents / self.total_agents

        # Round to get integer widths, ensuring we don't exceed bar_width
        completed_width = round(bar_width * completed_ratio)
        failed_width = round(bar_width * failed_ratio)
        running_width = round(bar_width * running_ratio)

        # Adjust if total exceeds bar_width due to rounding
        total_width = completed_width + failed_width + running_width
        if total_width > bar_width:
            # Trim from the largest segment
            if completed_width >= failed_width and completed_width >= running_width:
                completed_width -= total_width - bar_width
            elif failed_width >= running_width:
                failed_width -= total_width - bar_width
            else:
                running_width -= total_width - bar_width

        # Green for completed
        if completed_width > 0:
            bar_parts.append(f"[green]{'█' * completed_width}[/green]")

        # Red for failed
        if failed_width > 0:
            bar_parts.append(f"[red]{'█' * failed_width}[/red]")

        # Blue for running
        if running_width > 0:
            bar_parts.append(f"[blue]{'▒' * running_width}[/blue]")

        # Empty for remaining
        remaining = bar_width - completed_width - failed_width - running_width
        if remaining > 0:
            bar_parts.append(f"{'░' * remaining}")

        bar = "".join(bar_parts)
        percentage = int(progress_pct * 100)

        return f"Progress: {bar} {percentage}%"

    def update_agent_state(self, agent_name: str, state: AgentState) -> None:
        """Update the state of an agent.

        Args:
            agent_name: Name of the agent
            state: New state for the agent
        """
        self.agent_states[agent_name] = state

        # Update counters
        self.total_agents = len(self.agent_states)

        # Recalculate all counters
        self.running_agents = sum(
            1 for s in self.agent_states.values() if s in (AgentState.STARTING, AgentState.RUNNING)
        )
        self.completed_agents = sum(
            1 for s in self.agent_states.values() if s in (AgentState.COMPLETED, AgentState.READY)
        )
        self.failed_agents = sum(1 for s in self.agent_states.values() if s == AgentState.FAILED)

        # Update displays
        self._refresh_displays()

    def _refresh_displays(self) -> None:
        """Refresh the summary and progress displays."""
        summary_widget = self.query_one("#summary", Static)
        summary_widget.update(self._format_summary())

        progress_widget = self.query_one("#progress", Static)
        progress_widget.update(self._format_progress())

    def on_mount(self) -> None:
        """Called when the widget is mounted."""
        # Populate issue content if available
        if self.issue_body:
            self._populate_issue_content()

    def _populate_issue_content(self) -> None:
        """Populate the issue content log widget."""
        if not self.issue_body:
            return
        try:
            log_widget = self.query_one("#issue-content", Log)
            # Split content into lines and add to log
            for line in self.issue_body.split("\n"):
                log_widget.write(line + "\n")
        except NoMatches:
            # Widget might not be ready yet - defer until after refresh
            self.call_after_refresh(self._populate_issue_content)
