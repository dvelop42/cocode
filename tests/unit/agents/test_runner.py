"""Tests for cocode.agents.runner.AgentRunner."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

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

    # Mock StreamingSubprocess to avoid real subprocess execution
    with patch("cocode.agents.runner.StreamingSubprocess") as mock_streaming:
        mock_instance = MagicMock()
        mock_instance.run.return_value = 0
        mock_streaming.return_value = mock_instance

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
        
        # Verify StreamingSubprocess was called with correct parameters
        mock_streaming.assert_called_once()
        assert mock_streaming.call_args.kwargs["command"] == agent.get_command()
        assert mock_streaming.call_args.kwargs["cwd"] == tmp_path
        assert mock_streaming.call_args.kwargs["timeout"] == 10


def test_run_agent_env_filtering(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    fake_mgr = FakeTempManager(tmp_path)
    monkeypatch.setattr("cocode.agents.runner.get_temp_manager", lambda: fake_mgr)

    # Capture the environment passed to StreamingSubprocess
    captured_env = {}
    
    with patch("cocode.agents.runner.StreamingSubprocess") as mock_streaming:
        def capture_env(*args, **kwargs):
            captured_env.update(kwargs.get("env", {}))
            mock = MagicMock()
            mock.run.return_value = 0
            return mock
        
        mock_streaming.side_effect = capture_env

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

    assert captured_env["COCODE_REPO_PATH"] == str(tmp_path)
    assert captured_env["COCODE_ISSUE_NUMBER"] == "7"
    assert captured_env["COCODE_ISSUE_URL"] == "https://example/7"
    assert captured_env["COCODE_ISSUE_BODY_FILE"].endswith("issue-7.md")
    # PATH is overridden to safe path dirs
    assert captured_env["PATH"]
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
        for k in captured_env.keys()
    )


def test_run_agent_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    fake_mgr = FakeTempManager(tmp_path)
    monkeypatch.setattr("cocode.agents.runner.get_temp_manager", lambda: fake_mgr)

    with patch("cocode.agents.runner.StreamingSubprocess") as mock_streaming:
        mock_instance = MagicMock()
        mock_instance.run.side_effect = subprocess.TimeoutExpired(["sleep", "10"], 0.01)
        mock_streaming.return_value = mock_instance

        runner = AgentRunner()
        agent = DummyAgent(command=["/bin/sh", "-lc", "sleep 1"])

        status = runner.run_agent(
            agent=agent,
            worktree_path=tmp_path,
            issue_number=9,
            issue_body="body",
            issue_url="https://example/9",
            timeout=0,
        )

        assert status.exit_code == ExitCode.TIMEOUT
        assert status.ready is False
        assert "timeout" in (status.error_message or "").lower()


def test_run_agent_with_streaming_callbacks(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Test that streaming callbacks are properly invoked."""
    fake_mgr = FakeTempManager(tmp_path)
    monkeypatch.setattr("cocode.agents.runner.get_temp_manager", lambda: fake_mgr)

    stdout_lines = []
    stderr_lines = []
    
    def stdout_callback(line: str) -> None:
        stdout_lines.append(line)
    
    def stderr_callback(line: str) -> None:
        stderr_lines.append(line)

    with patch("cocode.agents.runner.StreamingSubprocess") as mock_streaming:
        mock_instance = MagicMock()
        
        # Simulate the streaming subprocess calling the callbacks
        def simulate_run(stdout_callback=None, stderr_callback=None):
            if stdout_callback:
                stdout_callback("line1")
                stdout_callback("line2")
            if stderr_callback:
                stderr_callback("error1")
            return 0
        
        mock_instance.run.side_effect = simulate_run
        mock_streaming.return_value = mock_instance

        runner = AgentRunner()
        agent = DummyAgent()

        status = runner.run_agent(
            agent=agent,
            worktree_path=tmp_path,
            issue_number=10,
            issue_body="test body",
            issue_url="https://example/10",
            timeout=10,
            stdout_callback=stdout_callback,
            stderr_callback=stderr_callback,
        )

        assert status.exit_code == 0
        assert stdout_lines == ["line1", "line2"]
        assert stderr_lines == ["error1"]


def test_run_agent_cancelled(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Test handling of cancelled agent execution."""
    fake_mgr = FakeTempManager(tmp_path)
    monkeypatch.setattr("cocode.agents.runner.get_temp_manager", lambda: fake_mgr)

    with patch("cocode.agents.runner.StreamingSubprocess") as mock_streaming:
        mock_instance = MagicMock()
        mock_instance.run.side_effect = KeyboardInterrupt("Process cancelled by user")
        mock_streaming.return_value = mock_instance

        runner = AgentRunner()
        agent = DummyAgent()

        status = runner.run_agent(
            agent=agent,
            worktree_path=tmp_path,
            issue_number=11,
            issue_body="test",
            issue_url="https://example/11",
            timeout=10,
        )

        assert status.exit_code == ExitCode.INTERRUPTED
        assert status.ready is False
        assert "cancelled" in (status.error_message or "").lower()
