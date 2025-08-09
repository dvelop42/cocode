#!/usr/bin/env python3
"""
Rich TUI Prototype for cocode
Demonstrates:
- Multiple agent panels with streaming logs
- Manual layout management
- Status indicators
- Ready detection
"""

import queue
import random
import threading
import time
from datetime import datetime

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text


class AgentMonitor:
    """Monitor for a single agent"""

    def __init__(self, name: str):
        self.name = name
        self.status = "⟳ Running"
        self.logs: list[str] = []
        self.max_logs = 20
        self.ready = False

    def add_log(self, message: str):
        """Add a log message"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[dim]{timestamp}[/dim] {message}")
        if len(self.logs) > self.max_logs:
            self.logs.pop(0)

    def set_ready(self):
        """Mark agent as ready"""
        self.ready = True
        self.status = "✓ Ready"
        self.add_log("[green]cocode ready for check[/green]")

    def get_panel(self) -> Panel:
        """Get Rich panel for display"""
        content = Text()

        # Status line
        if self.ready:
            content.append(f"Status: {self.status}\n", style="bold green")
        else:
            content.append(f"Status: {self.status}\n", style="bold yellow")

        content.append("-" * 40 + "\n", style="dim")

        # Logs
        for log in self.logs:
            content.append(log + "\n")

        return Panel(
            content,
            title=f"[bold]{self.name}[/bold]",
            border_style="green" if self.ready else "blue",
            padding=(1, 2),
        )


class CocodeRichApp:
    """Main TUI application using Rich"""

    def __init__(self):
        self.console = Console()
        self.agents: dict[str, AgentMonitor] = {
            "claude-code": AgentMonitor("Claude Code"),
            "codex-cli": AgentMonitor("Codex CLI"),
            "gpt-engineer": AgentMonitor("GPT Engineer"),
        }
        self.selected_agent = None
        self.running = True
        self.update_queue = queue.Queue()

    def create_layout(self) -> Layout:
        """Create the display layout"""
        layout = Layout()

        # Header
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=5),
        )

        # Header content
        header_text = Text("cocode - Multi-Agent Issue Solver", style="bold cyan")
        header_text.append(f"\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", style="dim")
        layout["header"].update(Panel(header_text))

        # Body with three agent panels
        layout["body"].split_row(
            Layout(self.agents["claude-code"].get_panel(), name="claude"),
            Layout(self.agents["codex-cli"].get_panel(), name="codex"),
            Layout(self.agents["gpt-engineer"].get_panel(), name="gpt"),
        )

        # Footer with controls
        controls = Table(show_header=False, box=None, padding=1)
        controls.add_row(
            "[bold]Commands:[/bold]",
            "1-3: Select agent",
            "r: Refresh",
            "p: Create PR",
            "q: Quit"
        )

        if self.selected_agent:
            controls.add_row(
                "[bold green]Selected:[/bold green]",
                self.selected_agent,
                "",
                "",
                "",
            )

        layout["footer"].update(Panel(controls, title="Controls"))

        return layout

    def simulate_agent_activity(self):
        """Background thread to simulate agent activity"""
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

        while self.running:
            time.sleep(0.5)

            for _agent_name, agent in self.agents.items():
                if random.random() > 0.3 and not agent.ready:
                    log_line = random.choice(log_samples)
                    agent.add_log(log_line)

                    # Randomly mark as ready
                    if random.random() > 0.95:
                        agent.set_ready()

            # Signal update needed
            self.update_queue.put("update")

    def handle_input(self):
        """Handle keyboard input (NOTE: blocks in this demo - a key limitation of Rich)"""
        try:
            key = self.console.input(timeout=0.1)  # This blocks - demonstrating Rich's limitation

            if key == "q":
                self.running = False
                return False
            elif key in ["1", "2", "3"]:
                agent_map = {"1": "claude-code", "2": "codex-cli", "3": "gpt-engineer"}
                self.selected_agent = agent_map[key]
                self.console.print(f"Selected: {self.selected_agent}", style="green")
            elif key == "r":
                for agent in self.agents.values():
                    agent.add_log("[dim]Refreshing status...[/dim]")
            elif key == "p" and self.selected_agent:
                self.agents[self.selected_agent].add_log(
                    "[bold green]Creating PR from branch...[/bold green]"
                )

        except Exception:
            pass

        return True

    def run(self):
        """Run the Rich TUI application"""
        # Start background simulation
        sim_thread = threading.Thread(target=self.simulate_agent_activity, daemon=True)
        sim_thread.start()

        with Live(self.create_layout(), console=self.console, refresh_per_second=2) as live:
            while self.running:
                # Check for updates
                try:
                    self.update_queue.get(timeout=0.1)
                    live.update(self.create_layout())
                except queue.Empty:
                    pass

                # Handle input (non-blocking in Rich is complex)
                # In a real implementation, we'd need a more sophisticated approach
                time.sleep(0.1)

        self.console.print("\n[bold]Exiting cocode...[/bold]")


def main():
    """Run the Rich prototype"""
    app = CocodeRichApp()

    console = Console()
    console.print("[bold cyan]Rich TUI Prototype for cocode[/bold cyan]")
    console.print("This demonstrates Rich's capabilities for building TUIs\n")

    # Show menu
    console.print("[bold]Options:[/bold]")
    console.print("1. Run TUI Demo")
    console.print("2. Show Layout Capabilities")
    console.print("3. Show Streaming Log Demo")

    choice = Prompt.ask("Select option", choices=["1", "2", "3"], default="1")

    if choice == "1":
        app.run()
    elif choice == "2":
        # Show layout capabilities
        layout = Layout()
        layout.split_column(
            Layout(Panel("Header Area", style="cyan"), size=3),
            Layout(name="body"),
            Layout(Panel("Footer Area", style="green"), size=3),
        )
        layout["body"].split_row(
            Layout(Panel("Agent 1", style="blue")),
            Layout(Panel("Agent 2", style="magenta")),
            Layout(Panel("Agent 3", style="yellow")),
        )
        console.print(layout)
    else:
        # Show streaming demo
        with Live(console=console, refresh_per_second=4) as live:
            for i in range(10):
                time.sleep(0.5)
                table = Table(title=f"Streaming Logs (Update {i+1})")
                table.add_column("Agent")
                table.add_column("Status")
                table.add_column("Last Log")

                for agent_name in ["claude-code", "codex-cli", "gpt-engineer"]:
                    table.add_row(
                        agent_name,
                        "⟳ Running" if i < 7 else "✓ Ready",
                        f"Processing step {i+1}..."
                    )

                live.update(table)


if __name__ == "__main__":
    main()
