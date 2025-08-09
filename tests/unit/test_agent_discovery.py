"""Unit tests for agent discovery."""

from cocode.agents.discovery import (
    AgentInfo,
    discover_agents,
    list_available_agents,
    which_agent,
)


def test_discover_agents_structure(monkeypatch):
    # Force no agents on PATH
    monkeypatch.setattr("shutil.which", lambda *_args, **_kw: None)
    infos = discover_agents()
    assert isinstance(infos, list)
    # Ensure we return AgentInfo entries for all known agents
    assert all(isinstance(i, AgentInfo) for i in infos)
    # None should be installed in this forced-missing scenario
    assert all(i.installed is False and i.path is None for i in infos)


def test_which_agent_prefers_first_alias(monkeypatch):
    calls: list[str] = []

    def fake_which(cmd: str):
        calls.append(cmd)
        # Pretend only the second alias exists for codex-cli
        if cmd == "codex":
            return "/usr/local/bin/codex"
        return None

    monkeypatch.setattr("shutil.which", fake_which)

    # unknown agent returns None
    assert which_agent("not-an-agent") is None

    # Known agent resolves to the found alias path
    path = which_agent("codex-cli")
    assert path == "/usr/local/bin/codex"
    # Ensure we only called which once for codex
    assert calls[:1] == ["codex"]


def test_list_available_agents_names_only(monkeypatch):
    # Pretend claude-code is available, codex is not
    def fake_which(cmd: str):
        if cmd == "claude-code":
            return "/usr/local/bin/claude-code"
        return None

    monkeypatch.setattr("shutil.which", fake_which)

    names = list_available_agents()
    assert "codex-cli" not in names
    assert "claude-code" not in names
