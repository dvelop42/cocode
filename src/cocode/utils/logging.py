"""Logging utilities."""

import logging
import re
from typing import Optional


class SecretRedactor:
    """Redact common secret patterns from logs."""
    
    PATTERNS = [
        # GitHub tokens
        (r'gh[ps]_[A-Za-z0-9]{36}', 'gh*_***'),
        # OpenAI/Anthropic tokens
        (r'sk-[A-Za-z0-9]{48}', 'sk-***'),
        (r'anthropic-[A-Za-z0-9]{40}', 'anthropic-***'),
        # JWT tokens
        (r'eyJ[A-Za-z0-9\-_]*\.[A-Za-z0-9\-_]*\.[A-Za-z0-9\-_]*', 'jwt-***'),
        # Database URLs
        (r'(postgres|mysql|mongodb)://[^@]+@[^/\s]+/\w+', r'\1://***:***@***/***'),
        # SSH private keys
        (r'-----BEGIN [A-Z ]+PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+PRIVATE KEY-----', '-----BEGIN PRIVATE KEY-----***-----END PRIVATE KEY-----'),
        # Generic API keys
        (r'api[_-]?key["\s:=]+["\'`]?([A-Za-z0-9_\-]{32,})', 'api_key=***'),
        # Bearer tokens
        (r'Bearer\s+[A-Za-z0-9\-._~+/]+=*', 'Bearer ***'),
        # AWS credentials
        (r'AKIA[0-9A-Z]{16}', 'AKIA***'),
        (r'aws[_-]?secret[_-]?access[_-]?key["\s:=]+["\'`]?([A-Za-z0-9/+=]{40})', 'aws_secret_access_key=***'),
        # Azure credentials
        (r'[a-z0-9]{8}-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{12}', 'azure-client-id-***'),
        (r'azure[_-]?client[_-]?secret["\s:=]+["\'`]?([A-Za-z0-9_\-]{34,})', 'azure_client_secret=***'),
        # Google Cloud service accounts
        (r'"private_key":\s*"-----BEGIN [A-Z ]+PRIVATE KEY-----[^"]+-----END [A-Z ]+PRIVATE KEY-----\\n"', '"private_key": "-----BEGIN PRIVATE KEY-----***-----END PRIVATE KEY-----"'),
        (r'[a-zA-Z0-9_-]{40,}@[a-zA-Z0-9-]+\.iam\.gserviceaccount\.com', '***@***.iam.gserviceaccount.com'),
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