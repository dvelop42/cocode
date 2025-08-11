"""Help overlay screen for displaying keyboard shortcuts."""

from collections.abc import Iterable

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Key
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static


class HelpScreen(ModalScreen[None]):
    """A simple modal screen showing keybindings."""

    CSS = """
    HelpScreen {
        align: center middle;
    }

    .dialog {
        border: round $primary;
        width: 80%;
        max-width: 100;
        background: $panel;
        padding: 1 2;
    }

    .title {
        content-align: center middle;
        margin-bottom: 1;
    }

    .bindings {
        height: auto;
    }

    .row {
        height: auto;
        margin: 0 0 1 0;
    }

    .key {
        width: 18;
        color: $accent;
    }

    .footer {
        content-align: center middle;
        margin-top: 1;
    }
    """

    BIND_KEYS = [
        ("Tab / Shift+Tab", "Cycle agents (next/prev)"),
        ("Left / Right", "Select previous/next agent"),
        ("1..9", "Select agent by number"),
        ("Up / Down", "Focus overview / agents"),
        ("Shift+Up / Shift+Down", "Scroll highlighted pane"),
        ("Ctrl+Up / Ctrl+Down", "Resize panes"),
        ("r / s", "Restart / Stop selected agent"),
        ("?", "Show this help"),
        ("q", "Quit (asks for confirmation)"),
        ("Ctrl+C", "Quit immediately"),
    ]

    def __init__(self, extra_bindings: Iterable[tuple[str, str]] | None = None) -> None:
        super().__init__()
        self._extra_bindings = list(extra_bindings or [])

    def compose(self) -> ComposeResult:
        all_bindings = self.BIND_KEYS + self._extra_bindings
        with Vertical(classes="dialog"):
            yield Label("[bold]Keyboard Shortcuts[/bold]", classes="title")
            with Vertical(classes="bindings"):
                for key, desc in all_bindings:
                    with Horizontal(classes="row"):
                        yield Label(f"{key}", classes="key")
                        yield Static(desc)
            with Horizontal(classes="footer"):
                yield Button("Close (Esc)", id="close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close":
            self.dismiss(None)

    def on_key(self, event: Key) -> None:
        # Close on Esc or ?
        if event.key in {"escape", "?"}:
            self.dismiss(None)
