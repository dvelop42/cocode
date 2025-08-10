"""Tests for cocode.agents.runner.AgentRunner."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from cocode.agents.base import Agent
from cocode.agents.runner import AgentRunner
from cocode.utils.exit_codes import ExitCode


class DummyAgent(Agent):
    def __init__(self, name: str = "dummy", ready: bool = True, command: list[str] | None = None):
        super().__init__(name)
        self._ready = ready
        self._command = command or ["/bin/sh", "-lc", "true"]

    def validate_environment(self) -> bool:  # pragma: no cover - unused in runner
        return True

    def prepare_environment(
        self, worktree_path: Path, issue_number: int, issue_body: str
    ) -> dict[str, str]:  # pragma: no cover - unused in runner
        return {}

    def get_command(self) -> list[str]:
        return list(self._command)

    def check_ready(self, worktree_path: Path) -> bool:
        return self._ready


class FakeTempManager:
    def __init__(self, path: Path):
        self._path = path
        self.written: list[Path] = []
        self.cleaned: list[Path] = []

    def write_issue_body(self, issue_number: int, body: str) -> Path:
        p = self._path / f"issue-{issue_number}.md"
        p.write_text(body)
        self.written.append(p)
        return p

    def cleanup_file(self, path: Path) -> None:
        self.cleaned.append(path)
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    def cleanup_all(self) -> None:  # pragma: no cover - not used in tests
        for p in list(self.written):
            self.cleanup_file(p)


def test_run_agent_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    fake_mgr = FakeTempManager(tmp_path)
    monkeypatch.setattr("cocode.agents.runner.get_temp_manager", lambda: fake_mgr)

    runner = AgentRunner()
    agent = DummyAgent()

    status = runner.run_agent(
        agent=agent,
        worktree_path=tmp_path,
        issue_number=42,
        issue_body="hello world",
        issue_url="https://example.com/issue/42",
        timeout=10,
    )

    assert status.exit_code == 0
    assert status.ready is True
    assert status.name == agent.name
    assert status.branch.endswith("42-dummy")
    # temp file should have been cleaned up
    assert fake_mgr.cleaned and fake_mgr.cleaned[0] in fake_mgr.written


def test_run_agent_env_filtering(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    captured: dict[str, Any] = {}

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess:
        captured.update(kwargs)
        return subprocess.CompletedProcess(args=["echo"], returncode=0, stdout="")

    fake_mgr = FakeTempManager(tmp_path)
    monkeypatch.setattr("cocode.agents.runner.get_temp_manager", lambda: fake_mgr)
    monkeypatch.setattr(subprocess, "run", fake_run)

    runner = AgentRunner()
    agent = DummyAgent(command=["/bin/sh", "-lc", "true"])

    _ = runner.run_agent(
        agent=agent,
        worktree_path=tmp_path,
        issue_number=7,
        issue_body="body",
        issue_url="https://example/7",
        timeout=5,
    )

    env = captured.get("env")
    assert isinstance(env, dict)
    assert env["COCODE_REPO_PATH"] == str(tmp_path)
    assert env["COCODE_ISSUE_NUMBER"] == "7"
    assert env["COCODE_ISSUE_URL"] == "https://example/7"
    assert env["COCODE_ISSUE_BODY_FILE"].endswith("issue-7.md")
    # PATH is overridden to safe path dirs
    assert env["PATH"]
    # ensure unapproved arbitrary variables aren't injected
    assert all(
        k.startswith("COCODE_")
        or k
        in {
            "LANG",
            "LC_ALL",
            "LC_CTYPE",
            "LC_MESSAGES",
            "LC_TIME",
            "TERM",
            "TERMINFO",
            "USER",
            "USERNAME",
            "TZ",
            "TMPDIR",
            "PATH",
        }
        for k in env.keys()
    )


def test_run_agent_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    def raise_timeout(*args: Any, **kwargs: Any) -> Any:
        raise subprocess.TimeoutExpired(cmd=["sleep", "10"], timeout=0.01)

    fake_mgr = FakeTempManager(tmp_path)
    monkeypatch.setattr("cocode.agents.runner.get_temp_manager", lambda: fake_mgr)
    monkeypatch.setattr(subprocess, "run", raise_timeout)

    runner = AgentRunner()
    agent = DummyAgent(command=["/bin/sh", "-lc", "sleep 1"])  # command won't run

    status = runner.run_agent(
        agent=agent,
        worktree_path=tmp_path,
        issue_number=9,
        issue_body="body",
        issue_url="https://example/9",
        timeout=0,  # immediate timeout
    )

    assert status.exit_code == ExitCode.TIMEOUT
    assert status.ready is False
    assert "timeout" in (status.error_message or "").lower()
