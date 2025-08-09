"""System dependency checks for cocode.

Provides lightweight checks for required tools and runtime:
- git: presence and version
- gh: presence (and version when available)
- python: interpreter path and version

These checks are intentionally side‑effect free and fast so they can be
consumed by the doctor command and other validators.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass


@dataclass
class DependencyInfo:
    """Basic information about a system dependency."""

    name: str
    installed: bool
    version: str | None = None
    path: str | None = None


def _which(cmd: str) -> str | None:
    """Return full path to executable if found on PATH, else None."""
    return shutil.which(cmd)


def _run_version_command(args: list[str]) -> str | None:
    """Run a version command and return a cleaned single-line string.

    Returns None if the command fails for any reason.
    """
    try:
        result = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
        )
        output = result.stdout.strip() or result.stderr.strip()
        return output or None
    except OSError:
        return None


def check_git() -> DependencyInfo:
    """Check for git presence and version."""
    path = _which("git")
    if not path:
        return DependencyInfo(name="git", installed=False)
    version = _run_version_command([path, "--version"]) or None
    return DependencyInfo(name="git", installed=True, version=version, path=path)


def check_gh() -> DependencyInfo:
    """Check for GitHub CLI presence (and version if available)."""
    path = _which("gh")
    if not path:
        return DependencyInfo(name="gh", installed=False)
    # `gh --version` prints multi-line output; keep the first line.
    raw = _run_version_command([path, "--version"]) or ""
    version = raw.splitlines()[0] if raw else None
    return DependencyInfo(name="gh", installed=True, version=version, path=path)


def check_python() -> DependencyInfo:
    """Return current Python interpreter information."""
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    return DependencyInfo(name="python", installed=True, version=version, path=sys.executable)


def check_all() -> list[DependencyInfo]:
    """Run all dependency checks and return results."""
    return [check_git(), check_gh(), check_python()]
