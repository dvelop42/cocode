"""GitHub authentication checker using the gh CLI.

This module provides a small helper to determine whether the user is
authenticated with GitHub via the GitHub CLI (`gh`) and, if so,
extracts the username and auth method from the CLI output.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass


@dataclass
class AuthStatus:
    """Represents GitHub CLI authentication status."""

    authenticated: bool
    host: str | None = None
    username: str | None = None
    auth_method: str | None = None
    raw_output: str | None = None
    error: str | None = None


_LOGGED_IN_RE = re.compile(
    r"Logged in to (?P<host>\S+) as (?P<user>[\w-]+) \((?P<method>[^)]+)\)",
)


def get_auth_status() -> AuthStatus:
    """Return GitHub authentication status via `gh auth status`.

    The function executes `gh auth status` and parses the output for a line like:

        "Logged in to github.com as alice (oauth_token)"

    Returns a best-effort parse. If `gh` is not installed or returns a non-zero
    exit code that indicates not logged in, `authenticated` will be False with
    `error` best-effort populated.
    """
    try:
        proc = subprocess.run(
            ["gh", "auth", "status"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except FileNotFoundError:
        return AuthStatus(
            authenticated=False,
            error="GitHub CLI (gh) not found on PATH",
        )
    except OSError as e:
        return AuthStatus(
            authenticated=False,
            error=str(e),
        )

    # gh prints info to stdout; errors/instructions may be on stderr
    output = proc.stdout or ""
    err = proc.stderr or ""
    combined = (output + ("\n" + err if err else "")).strip()

    if proc.returncode == 0:
        # Look for the logged-in line; gh may include a leading host line
        match = _LOGGED_IN_RE.search(combined)
        if match:
            return AuthStatus(
                authenticated=True,
                host=match.group("host"),
                username=match.group("user"),
                auth_method=match.group("method"),
                raw_output=combined or None,
            )
        # Fallback: authenticated but unparsed details
        return AuthStatus(
            authenticated=True,
            raw_output=combined or None,
        )

    # Non-zero exit often means not logged in
    return AuthStatus(
        authenticated=False,
        raw_output=combined or None,
        error=(err or output).strip() or None,
    )
