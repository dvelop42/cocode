"""Main TUI application using Textual."""

import asyncio
from collections.abc import Callable

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.reactive import reactive
from textual.widgets import Footer, Header, Static

from cocode.agents.base import AgentStatus
from cocode.agents.lifecycle import AgentLifecycleManager, AgentState
from cocode.tui.agent_panel import AgentPanel
from cocode.tui.confirm_quit import ConfirmQuitScreen
from cocode.tui.help_overlay import HelpScreen
from cocode.tui.overview_panel import OverviewPanel


class CocodeApp(App):
    """Main TUI application for monitoring agents."""

    # Configuration constants
    DEFAULT_UPDATE_INTERVAL = 0.5  # seconds, can be made configurable via settings in future

    CSS = """
    .dry-run-indicator {
        background: $warning;
        color: $warning-lighten-3;
        dock: top;
        height: 1;
    }

    .content {
        height: 1fr;
    }

    #top-pane {
        height: 30%;
        min-height: 8;
        border-bottom: solid $primary;
    }

    #bottom-pane {
        height: 70%;
        min-height: 10;
    }

    OverviewPanel {
        border: solid $primary;
        height: 100%;
        padding: 1;
    }

    OverviewPanel:focus {
        border: thick $accent;
    }

    .issue-header {
        margin: 1;
    }

    .issue-url {
        margin-left: 1;
        margin-bottom: 1;
    }

    .separator {
        margin: 1 0;
        color: $primary-lighten-2;
    }

    .section-header {
        margin: 1;
        color: $accent;
    }

    #issue-content {
        margin: 1;
        height: auto;
        max-height: 50%;
        border: none;
    }

    AgentPanel {
        border: solid $primary;
        height: 100%;
        width: 1fr;
        padding: 1;
    }

    AgentPanel:focus {
        border: thick $accent;
    }

    AgentPanel.selected {
        border: thick $accent;
        background: $boost;
    }

    AgentPanel.selected.failed {
        border: thick $error;
        background: $boost;
    }

    AgentPanel.selected.ready {
        border: thick $success;
        background: $boost;
    }

    AgentPanel.failed {
        border: solid $error;
    }

    AgentPanel.ready {
        border: solid $success-lighten-2;
    }

    #agent-container {
        height: 100%;
    }

    .pane-resizer {
        background: $primary;
        dock: bottom;
        height: 1;
    }
    """

    BINDINGS = [
        Binding("q", "request_quit", "Quit"),
        Binding("ctrl+c", "quit", "Quit Now"),
        Binding("r", "restart_agent", "Restart"),
        Binding("s", "stop_agent", "Stop"),
        Binding("left", "previous_agent", "Previous"),
        Binding("right", "next_agent", "Next"),
        Binding("tab", "next_agent", "Next Agent"),
        Binding("shift+tab", "previous_agent", "Prev Agent"),
        Binding("ctrl+up", "resize_pane_up", "Grow Top Pane"),
        Binding("ctrl+down", "resize_pane_down", "Grow Bottom Pane"),
        Binding("ctrl+o", "focus_overview", "Focus Overview"),
        Binding("ctrl+a", "focus_agents", "Focus Agents"),
        # Vim-like bindings
        Binding("h", "previous_agent", "Prev (vim)"),
        Binding("l", "next_agent", "Next (vim)"),
        Binding("j", "focus_agents", "Focus Agents (vim)"),
        Binding("k", "focus_overview", "Focus Overview (vim)"),
        Binding("g", "first_agent", "First Agent (vim)"),
        Binding("G", "last_agent", "Last Agent (vim)"),
        # Help overlay
        Binding("?", "show_help", "Help"),
    ]

    # Reactive attributes
    dry_run = reactive(False)
    selected_agent_index = reactive(0)
    top_pane_height = reactive(30)  # Percentage of screen height
    MIN_PANE_HEIGHT = 15  # Minimum percentage for any pane
    MAX_PANE_HEIGHT = 70  # Maximum percentage for any pane

    def __init__(
        self,
        lifecycle_manager: AgentLifecycleManager | None = None,
        issue_number: int = 0,
        issue_body: str = "",
        issue_url: str = "",
        dry_run: bool = False,
        update_interval: float | None = None,
        **kwargs: object,
    ) -> None:
        """Initialize the app.

        Args:
            lifecycle_manager: Agent lifecycle manager instance
            issue_number: GitHub issue number
            issue_body: Issue body content
            issue_url: URL to the GitHub issue
            dry_run: Whether the app is in dry run mode.
            update_interval: Optional update interval in seconds (defaults to DEFAULT_UPDATE_INTERVAL)
            **kwargs: Additional arguments for App.
        """
        super().__init__(**kwargs)
        self.lifecycle_manager = lifecycle_manager or AgentLifecycleManager()
        self.issue_number = issue_number
        self.issue_body = issue_body
        self.issue_url = issue_url
        self.dry_run = dry_run
        self.update_interval = update_interval or self.DEFAULT_UPDATE_INTERVAL
        self.agent_panels: list[AgentPanel] = []
        self.overview_panel: OverviewPanel | None = None
        self.update_task: asyncio.Task[None] | None = None

    def compose(self) -> ComposeResult:
        """Compose the TUI layout."""
        yield Header()

        if self.dry_run:
            yield Static(
                "🔍 DRY RUN MODE - No changes will be made",
                classes="dry-run-indicator",
                id="dry-run-indicator",
            )

        with Container(classes="content"):
            # Top pane with overview
            with VerticalScroll(id="top-pane"):
                self.overview_panel = OverviewPanel(
                    self.issue_number,
                    self.issue_url,
                    self.issue_body,
                )
                yield self.overview_panel

            # Bottom pane with agent panels
            with VerticalScroll(id="bottom-pane"):
                with Horizontal(id="agent-container"):
                    # Create panels for registered agents
                    for agent_name in self.lifecycle_manager.agents:
                        panel = AgentPanel(agent_name)
                        self.agent_panels.append(panel)
                        yield panel

                    # If no agents, show placeholder
                    if not self.agent_panels:
                        yield Static(
                            "No agents registered. Use 'cocode init' to configure agents.",
                            id="no-agents",
                        )

        yield Footer()

    def on_mount(self) -> None:
        """Called when app is mounted."""
        if self.dry_run:
            self.title = "Cocode - DRY RUN MODE"
        elif self.issue_number:
            self.title = f"Cocode - Issue #{self.issue_number}"
        else:
            self.title = "Cocode"

        # Focus overview panel initially
        if self.overview_panel:
            self.overview_panel.focus()

        # Select first agent if available (but don't focus yet)
        if self.agent_panels:
            self.agent_panels[0].set_selected(True)

            # Dynamically bind number keys for agent selection (up to 9 agents)
            for i, panel in enumerate(self.agent_panels[:9], 1):
                self.bind(
                    str(i), f"select_agent({i-1})", description=f"Agent {i}: {panel.agent_name}"
                )

        # Start update loop only if we have an event loop (not in tests)
        # In test environments, asyncio.get_running_loop() raises RuntimeError
        # since tests often run synchronously without an active event loop
        try:
            loop = asyncio.get_running_loop()
            self.update_task = loop.create_task(self._update_loop())
        except RuntimeError:
            # No event loop available (typically in unit tests)
            # This allows tests to run synchronously without requiring async setup
            self.update_task = None

    async def _update_loop(self) -> None:
        """Update agent states periodically."""
        while True:
            try:
                # Batch collect all agent states first
                agent_updates = []
                for panel in self.agent_panels:
                    info = self.lifecycle_manager.get_agent_info(panel.agent_name)
                    if info:
                        agent_updates.append((panel, info))

                # Apply all UI updates in a single batch
                # This reduces the number of render cycles
                with self.batch_update():
                    for panel, info in agent_updates:
                        panel.update_state(info.state)

                        # Update panel border based on state
                        panel.remove_class("failed", "ready")
                        if info.state == AgentState.FAILED:
                            panel.add_class("failed")
                        elif info.state == AgentState.READY:
                            panel.add_class("ready")

                        # Update overview panel with agent state
                        if self.overview_panel:
                            self.overview_panel.update_agent_state(panel.agent_name, info.state)

                await asyncio.sleep(self.update_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.log.error(f"Error in update loop: {e}")
                await asyncio.sleep(1)

    def action_restart_agent(self) -> None:
        """Restart the selected agent."""
        if not self.agent_panels or self.dry_run:
            return

        selected_panel = self.agent_panels[self.selected_agent_index]
        agent_name = selected_panel.agent_name

        # Clear logs
        selected_panel.clear_logs()
        selected_panel.add_log_line("[yellow]Restarting agent...[/yellow]")

        # Restart agent
        on_stdout, on_stderr, on_completion = self._make_panel_callbacks(selected_panel)

        success = self.lifecycle_manager.restart_agent(
            agent_name,
            self.issue_number,
            self.issue_body,
            self.issue_url,
            stdout_callback=on_stdout,
            stderr_callback=on_stderr,
            completion_callback=on_completion,
        )

        if not success:
            selected_panel.add_log_line("[red]Failed to restart agent[/red]")

    def action_stop_agent(self) -> None:
        """Stop the selected agent."""
        if not self.agent_panels or self.dry_run:
            return

        selected_panel = self.agent_panels[self.selected_agent_index]
        agent_name = selected_panel.agent_name

        success = self.lifecycle_manager.stop_agent(agent_name)
        if success:
            selected_panel.add_log_line("[yellow]Agent stopped[/yellow]")
        else:
            selected_panel.add_log_line("[red]Failed to stop agent[/red]")

    def action_next_agent(self) -> None:
        """Select the next agent."""
        if not self.agent_panels:
            return

        self.agent_panels[self.selected_agent_index].set_selected(False)
        self.selected_agent_index = (self.selected_agent_index + 1) % len(self.agent_panels)
        self.agent_panels[self.selected_agent_index].set_selected(True)
        # Ensure the selected panel is visible and focused
        self.agent_panels[self.selected_agent_index].focus()
        self.agent_panels[self.selected_agent_index].scroll_visible()

    def action_previous_agent(self) -> None:
        """Select the previous agent."""
        if not self.agent_panels:
            return

        self.agent_panels[self.selected_agent_index].set_selected(False)
        self.selected_agent_index = (self.selected_agent_index - 1) % len(self.agent_panels)
        self.agent_panels[self.selected_agent_index].set_selected(True)
        # Ensure the selected panel is visible and focused
        self.agent_panels[self.selected_agent_index].focus()
        self.agent_panels[self.selected_agent_index].scroll_visible()

    def action_select_agent(self, index: int) -> None:
        """Select an agent by index.

        Args:
            index: Agent index to select
        """
        if not self.agent_panels or index >= len(self.agent_panels):
            return

        self.agent_panels[self.selected_agent_index].set_selected(False)
        self.selected_agent_index = index
        self.agent_panels[self.selected_agent_index].set_selected(True)
        # Ensure the selected panel is visible and focused
        self.agent_panels[self.selected_agent_index].focus()
        self.agent_panels[self.selected_agent_index].scroll_visible()

    def action_resize_pane_up(self) -> None:
        """Increase the top pane size (decrease bottom pane)."""
        new_height = self.top_pane_height + 5
        if new_height <= self.MAX_PANE_HEIGHT:
            self.top_pane_height = new_height
            self._update_pane_sizes()

    def action_resize_pane_down(self) -> None:
        """Decrease the top pane size (increase bottom pane)."""
        new_height = self.top_pane_height - 5
        if new_height >= self.MIN_PANE_HEIGHT:
            self.top_pane_height = new_height
            self._update_pane_sizes()

    def action_focus_overview(self) -> None:
        """Focus the overview panel."""
        if self.overview_panel:
            self.overview_panel.focus()

    def action_focus_agents(self) -> None:
        """Focus the agent panels."""
        if self.agent_panels:
            self.agent_panels[self.selected_agent_index].focus()
            # Selection state already indicates active pane

    def action_first_agent(self) -> None:
        """Select the first agent (vim 'g')."""
        if not self.agent_panels:
            return
        self.action_select_agent(0)

    def action_last_agent(self) -> None:
        """Select the last agent (vim 'G')."""
        if not self.agent_panels:
            return
        self.action_select_agent(len(self.agent_panels) - 1)

    def action_show_help(self) -> None:
        """Show the help overlay with keyboard shortcuts."""
        self.push_screen(HelpScreen())

    async def action_request_quit(self) -> None:
        """Ask for confirmation before quitting."""
        result = await self.push_screen_wait(ConfirmQuitScreen())
        if result:
            await self.shutdown()  # ensure cleanup via on_shutdown
            self.exit()

    def _update_pane_sizes(self) -> None:
        """Update the CSS for pane sizes based on current settings."""
        top_pane = self.query_one("#top-pane")
        bottom_pane = self.query_one("#bottom-pane")

        # Calculate actual heights
        bottom_height = 100 - self.top_pane_height

        # Update styles
        top_pane.styles.height = f"{self.top_pane_height}%"
        bottom_pane.styles.height = f"{bottom_height}%"

    def start_all_agents(self) -> None:
        """Start all registered agents."""
        for panel in self.agent_panels:
            agent_name = panel.agent_name

            on_stdout, on_stderr, on_completion = self._make_panel_callbacks(panel)

            success = self.lifecycle_manager.start_agent(
                agent_name,
                self.issue_number,
                self.issue_body,
                self.issue_url,
                stdout_callback=on_stdout,
                stderr_callback=on_stderr,
                completion_callback=on_completion,
            )

            if success:
                panel.add_log_line("[blue]Agent started[/blue]")
                # Initialize overview panel with agent state
                if self.overview_panel:
                    self.overview_panel.update_agent_state(agent_name, AgentState.STARTING)
            else:
                panel.add_log_line("[red]Failed to start agent[/red]")
                if self.overview_panel:
                    self.overview_panel.update_agent_state(agent_name, AgentState.FAILED)

    async def on_shutdown(self) -> None:
        """Handle app shutdown."""
        # Cancel update task
        if self.update_task:
            self.update_task.cancel()
            try:
                await self.update_task
            except asyncio.CancelledError:
                pass

        # Shutdown all agents
        self.lifecycle_manager.shutdown_all()

    def _make_panel_callbacks(
        self, panel: AgentPanel
    ) -> tuple[Callable[[str], None], Callable[[str], None], Callable[[AgentStatus], None]]:
        """Create unified stdout/stderr/completion callbacks for a panel."""

        def on_stdout(line: str) -> None:
            panel.add_log_line(line)

        def on_stderr(line: str) -> None:
            panel.add_log_line(f"[red]{line}[/red]")

        def on_completion(status: AgentStatus) -> None:
            if status.ready:
                panel.add_log_line("[green]Agent ready![/green]")
            elif status.exit_code == 0:
                panel.add_log_line("[green]Agent completed successfully[/green]")
            else:
                panel.add_log_line(f"[red]Agent failed: {status.error_message}[/red]")

        return on_stdout, on_stderr, on_completion
