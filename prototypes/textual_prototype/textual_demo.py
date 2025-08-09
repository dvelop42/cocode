#!/usr/bin/env python3
"""
Textual TUI Prototype for cocode
Demonstrates:
- Multiple agent panels with streaming logs
- Keyboard navigation
- Status indicators
- Ready detection
"""

import random
from datetime import datetime

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Footer, Header, Log, Static


class AgentPanel(Static):
    """Panel for a single agent showing status and logs"""

    status = reactive("⟳ Running")

    def __init__(self, agent_name: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.agent_name = agent_name
        self.log_lines: list[str] = []
        self.border_title = f"Agent: {agent_name}"

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(f"[bold]{self.agent_name}[/bold]", id=f"title-{self.agent_name}")
            yield Static(self.status, id=f"status-{self.agent_name}")
            yield Log(id=f"log-{self.agent_name}", auto_scroll=True, max_lines=100)

    def add_log_line(self, line: str):
        """Add a line to the agent's log"""
        log_widget = self.query_one(f"#log-{self.agent_name}", Log)
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_widget.write_line(f"[dim]{timestamp}[/dim] {line}")

    def set_status(self, status: str):
        """Update agent status"""
        self.status = status
        status_widget = self.query_one(f"#status-{self.agent_name}", Static)
        status_widget.update(status)


class CocodeTextualApp(App):
    """Main TUI application using Textual"""

    CSS = """
    AgentPanel {
        border: solid green;
        height: 100%;
        padding: 1;
    }

    #status-claude-code {
        color: cyan;
    }

    #status-codex-cli {
        color: magenta;
    }

    #status-gpt-engineer {
        color: yellow;
    }

    Log {
        height: 100%;
        background: $surface;
        border: solid $primary-lighten-1;
        overflow-y: auto;
    }

    Button {
        margin: 1;
        width: 20;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("1", "select_agent('claude-code')", "Select Claude"),
        ("2", "select_agent('codex-cli')", "Select Codex"),
        ("3", "select_agent('gpt-engineer')", "Select GPT"),
        ("r", "refresh", "Refresh"),
        ("p", "create_pr", "Create PR"),
    ]

    def __init__(self):
        super().__init__()
        self.agents: dict[str, AgentPanel] = {}
        self.selected_agent = None

    def compose(self) -> ComposeResult:
        """Create the UI layout"""
        yield Header(show_clock=True)

        with Horizontal():
            # Create three agent panels
            for agent_name in ["claude-code", "codex-cli", "gpt-engineer"]:
                panel = AgentPanel(agent_name)
                self.agents[agent_name] = panel
                yield panel

        with Horizontal(id="controls"):
            yield Button("Select Best", id="select-btn")
            yield Button("Create PR", id="create-pr-btn", variant="success")
            yield Button("Cancel All", id="cancel-btn", variant="error")

        yield Footer()

    async def on_mount(self) -> None:
        """Start simulating agent activity when app starts"""
        self.set_timer(0.5, self.simulate_agent_activity)

    def simulate_agent_activity(self):
        """Simulate streaming logs from agents"""
        log_samples = [
            "Analyzing issue #79...",
            "Fetching repository context...",
            "Understanding codebase structure...",
            "Implementing TUI framework...",
            "Running tests...",
            "Checking code style...",
            "Building prototype...",
            "Validating solution...",
        ]

        for _agent_name, panel in self.agents.items():
            if random.random() > 0.3:  # 70% chance of activity
                log_line = random.choice(log_samples)
                panel.add_log_line(log_line)

                # Randomly mark as ready
                if random.random() > 0.95:
                    panel.set_status("✓ Ready")
                    panel.add_log_line("[green]cocode ready for check[/green]")

        # Continue simulation
        self.set_timer(0.5, self.simulate_agent_activity)

    def action_select_agent(self, agent_name: str):
        """Select an agent"""
        self.selected_agent = agent_name
        for name, panel in self.agents.items():
            if name == agent_name:
                panel.border_subtitle = "✓ SELECTED"
            else:
                panel.border_subtitle = ""

    def action_create_pr(self):
        """Create a PR with selected agent"""
        if self.selected_agent:
            self.agents[self.selected_agent].add_log_line(
                f"[bold green]Creating PR from {self.selected_agent} branch...[/bold green]"
            )

    def action_refresh(self):
        """Refresh agent status"""
        for panel in self.agents.values():
            panel.add_log_line("[dim]Refreshing status...[/dim]")


def main():
    """Run the Textual prototype"""
    app = CocodeTextualApp()
    app.run()


if __name__ == "__main__":
    main()
