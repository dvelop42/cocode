"""Main TUI application using Textual."""

import asyncio
from collections.abc import Callable

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.reactive import reactive
from textual.widgets import Footer, Header, Static

from cocode.agents.base import AgentStatus
from cocode.agents.lifecycle import AgentLifecycleManager, AgentState
from cocode.tui.agent_panel import AgentPanel


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
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "restart_agent", "Restart"),
        Binding("s", "stop_agent", "Stop"),
        Binding("left", "previous_agent", "Previous"),
        Binding("right", "next_agent", "Next"),
        Binding("tab", "next_agent", "Next Agent"),
        Binding("shift+tab", "previous_agent", "Prev Agent"),
    ]

    # Reactive attributes
    dry_run = reactive(False)
    selected_agent_index = reactive(0)

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

        # Select and focus first agent if available
        if self.agent_panels:
            self.agent_panels[0].set_selected(True)
            self.agent_panels[0].focus()

            # Dynamically bind number keys for agent selection (up to 9 agents)
            for i, panel in enumerate(self.agent_panels[:9], 1):
                self.bind(
                    str(i), f"select_agent({i-1})", description=f"Agent {i}: {panel.agent_name}"
                )

        # Start update loop only if we have an event loop (not in tests)
        try:
            loop = asyncio.get_running_loop()
            self.update_task = loop.create_task(self._update_loop())
        except RuntimeError:
            # No event loop available (e.g., in tests)
            self.update_task = None

    async def _update_loop(self) -> None:
        """Update agent states periodically."""
        while True:
            try:
                for panel in self.agent_panels:
                    info = self.lifecycle_manager.get_agent_info(panel.agent_name)
                    if info:
                        panel.update_state(info.state)

                        # Update panel border based on state
                        panel.remove_class("failed", "ready")
                        if info.state == AgentState.FAILED:
                            panel.add_class("failed")
                        elif info.state == AgentState.READY:
                            panel.add_class("ready")

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
        def on_stdout(line: str) -> None:
            selected_panel.add_log_line(line)

        def on_stderr(line: str) -> None:
            selected_panel.add_log_line(f"[red]{line}[/red]")

        def on_completion(status: AgentStatus) -> None:
            if status.ready:
                selected_panel.add_log_line("[green]Agent ready![/green]")
            elif status.exit_code == 0:
                selected_panel.add_log_line("[green]Agent completed successfully[/green]")
            else:
                selected_panel.add_log_line(f"[red]Agent failed: {status.error_message}[/red]")

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

    def start_all_agents(self) -> None:
        """Start all registered agents."""
        for panel in self.agent_panels:
            agent_name = panel.agent_name

            def make_stdout_callback(p: AgentPanel) -> Callable:
                def callback(line: str) -> None:
                    p.add_log_line(line)

                return callback

            def make_stderr_callback(p: AgentPanel) -> Callable:
                def callback(line: str) -> None:
                    p.add_log_line(f"[red]{line}[/red]")

                return callback

            def make_completion_callback(p: AgentPanel) -> Callable:
                def callback(status: AgentStatus) -> None:
                    if status.ready:
                        p.add_log_line("[green]Agent ready![/green]")
                    elif status.exit_code == 0:
                        p.add_log_line("[green]Agent completed successfully[/green]")
                    else:
                        p.add_log_line(f"[red]Agent failed: {status.error_message}[/red]")

                return callback

            on_stdout = make_stdout_callback(panel)
            on_stderr = make_stderr_callback(panel)
            on_completion = make_completion_callback(panel)

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
            else:
                panel.add_log_line("[red]Failed to start agent[/red]")

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
