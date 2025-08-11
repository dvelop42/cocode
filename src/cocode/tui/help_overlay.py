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
        ("r / s", "Restart / Stop selected agent"),
        ("?", "Show this help"),
        ("q", "Quit (asks for confirmation)"),
        ("Ctrl+C", "Quit immediately"),
    ]

    def __init__(self, extra_bindings: Iterable[tuple[str, str]] | None = None) -> None:
        super().__init__()
        self._extra_bindings = self._sanitize_bindings(extra_bindings or [])

    @staticmethod
    def _sanitize_bindings(bindings: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
        """Validate and normalize extra binding entries.

        - Ensure each entry is a (str, str) tuple
        - Strip newlines and trim to reasonable lengths
        - Ignore malformed entries
        """
        sanitized: list[tuple[str, str]] = []
        for item in bindings:
            if not isinstance(item, tuple) or len(item) != 2:
                continue
            key, desc = item
            if not isinstance(key, str) or not isinstance(desc, str):
                continue
            key = key.replace("\n", " ").strip()[:40]
            desc = desc.replace("\n", " ").strip()[:80]
            sanitized.append((key, desc))
        return sanitized

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
            try:
                self.dismiss(None)
            except Exception:
                pass

    def on_key(self, event: Key) -> None:
        # Close on Esc or ?
        if event.key in {"escape", "?"}:
            self.dismiss(None)
