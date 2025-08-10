"""Main TUI application using Textual."""

from textual.app import App
from textual.reactive import reactive
from textual.widgets import Header, Footer, Static
from textual.containers import Container, Horizontal


class CocodeApp(App):
    """Main TUI application for monitoring agents."""
    
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
    """
    
    # Reactive attributes
    dry_run = reactive(False)
    
    def __init__(self, dry_run: bool = False, **kwargs):
        """Initialize the app.
        
        Args:
            dry_run: Whether the app is in dry run mode.
            **kwargs: Additional arguments for App.
        """
        super().__init__(**kwargs)
        self.dry_run = dry_run

    def compose(self):
        """Compose the TUI layout."""
        yield Header()
        
        if self.dry_run:
            yield Static(
                "🔍 DRY RUN MODE - No changes will be made", 
                classes="dry-run-indicator",
                id="dry-run-indicator"
            )
        
        with Container(classes="content"):
            yield Static("Agent monitoring interface (placeholder)", id="main-content")
            
        yield Footer()

    def on_mount(self) -> None:
        """Called when app is mounted."""
        if self.dry_run:
            self.title = "Cocode - DRY RUN MODE"
        else:
            self.title = "Cocode"
