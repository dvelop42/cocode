"""Logging utilities."""

import logging
import re
from typing import Optional


class SecretRedactor:
    """Redact common secret patterns from logs."""
    
    PATTERNS = [
        (r'gh[ps]_[A-Za-z0-9]{36}', 'gh*_***'),
        (r'sk-[A-Za-z0-9]{48}', 'sk-***'),
        (r'anthropic-[A-Za-z0-9]{40}', 'anthropic-***'),
        (r'eyJ[A-Za-z0-9\-_]*\.[A-Za-z0-9\-_]*\.[A-Za-z0-9\-_]*', 'jwt-***'),
    ]
    
    def redact(self, text: str) -> str:
        """Redact secrets from text."""
        for pattern, replacement in self.PATTERNS:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return text


def setup_logging(level: str = "INFO") -> None:
    """Set up logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )