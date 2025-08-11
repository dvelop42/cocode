"""Confirmation modal for quitting the application."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.events import Key
from textual.screen import ModalScreen
from textual.widgets import Label


class ConfirmQuitScreen(ModalScreen[bool]):
    """Modal that asks user to confirm quitting."""

    CSS = """
    ConfirmQuitScreen {
        align: center middle;
    }

    .dialog {
        border: round $error;
        width: 40%;
        max-width: 60;
        height: auto;
        max-height: 7;
        background: $panel;
        padding: 1 2;
        content-align: center middle;
    }

    .dialog Label {
        margin: 0;
    }

    .title {
        margin-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label("[bold]Quit cocode?[/bold]", classes="title")
            yield Label("All running agents will be asked to stop.")
            yield Label("Press [bold]Y[/bold] to confirm or [bold]N[/bold]/Esc to cancel.")

    def on_key(self, event: Key) -> None:
        key = event.key.lower()
        if key in {"escape", "n"}:
            self.dismiss(False)
        elif key in {"enter", "y"}:
            self.dismiss(True)
