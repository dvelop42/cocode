"""Configuration file management."""

from pathlib import Path
from typing import Any


class ConfigManager:
    """Manages cocode configuration."""

    def __init__(self, config_path: Path | None = None):
        """Initialize config manager."""
        self.config_path = config_path or Path(".cocode/config.json")

    def load(self) -> dict[str, Any]:
        """Load configuration."""
        raise NotImplementedError("Config loading not yet implemented")

    def save(self, config: dict[str, Any]) -> None:
        """Save configuration."""
        raise NotImplementedError("Config saving not yet implemented")
