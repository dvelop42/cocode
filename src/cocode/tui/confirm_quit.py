"""Confirmation modal for quitting the application."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Key
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class ConfirmQuitScreen(ModalScreen[bool]):
    """Modal that asks user to confirm quitting."""

    CSS = """
    ConfirmQuitScreen {
        align: center middle;
    }

    .dialog {
        border: round $error;
        width: 60%;
        max-width: 80;
        background: $panel;
        padding: 1 2;
    }

    .buttons {
        content-align: center middle;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label("[bold]Quit cocode?[/bold]")
            yield Label("All running agents will be asked to stop.")
            with Horizontal(classes="buttons"):
                yield Button("Yes", variant="error", id="yes")
                yield Button("No", variant="primary", id="no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")

    def on_key(self, event: Key) -> None:
        key = event.key
        if key in {"escape", "n"}:
            self.dismiss(False)
        elif key in {"enter", "y"}:
            self.dismiss(True)
