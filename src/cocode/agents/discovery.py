"""Agent discovery utilities.

Discovers supported agent CLIs on PATH and reports availability.

This MVP keeps a small, explicit catalog of known agents and checks for
their primary command (and optional aliases) using `shutil.which`.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass


@dataclass
class AgentInfo:
    """Information about a known agent and its availability."""

    name: str
    installed: bool
    path: str | None = None
    aliases: list[str] | None = None


# Minimal catalog of known agents and their CLI entry points
_KNOWN_AGENTS: dict[str, list[str]] = {
    # Primary command followed by optional aliases, in preferred order
    # Note: real CLIs are commonly "claude" and "codex"
    "claude-code": ["claude", "claude-code"],
    "codex-cli": ["codex", "codex-cli"],
}


def _first_on_path(candidates: list[str]) -> str | None:
    """Return the first candidate found on PATH, else None."""
    for cmd in candidates:
        path = shutil.which(cmd)
        if path:
            return path
    return None


def discover_agents() -> list[AgentInfo]:
    """Discover known agents on PATH.

    Returns a list of AgentInfo for every known agent, marking whether
    it is installed and the resolved path if found.
    """
    results: list[AgentInfo] = []
    for name, commands in _KNOWN_AGENTS.items():
        path = _first_on_path(commands)
        results.append(
            AgentInfo(name=name, installed=bool(path), path=path, aliases=commands)
        )
    return results


def list_available_agents() -> list[str]:
    """Return names of agents available on PATH."""
    return [info.name for info in discover_agents() if info.installed]


def which_agent(name: str) -> str | None:
    """Return resolved path to an agent command or None if not found.

    Looks up the known command names for `name` and returns the first that
    exists on PATH.
    """
    commands = _KNOWN_AGENTS.get(name)
    if not commands:
        return None
    return _first_on_path(commands)
