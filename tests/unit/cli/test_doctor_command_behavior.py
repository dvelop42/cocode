"""Behavior tests for doctor command with monkeypatched dependencies."""

from __future__ import annotations

import types

import pytest
import typer

from cocode.cli.doctor import doctor_command
from cocode.utils.dependencies import DependencyInfo
from cocode.utils.exit_codes import ExitCode


def _fake_auth(authenticated: bool = True, host: str | None = "github.com") -> object:
    return types.SimpleNamespace(
        authenticated=authenticated,
        host=host,
        username="someone" if authenticated else None,
        auth_method="oauth" if authenticated else None,
        error=None if authenticated else "not logged in",
    )


def test_doctor_missing_required_deps(monkeypatch: pytest.MonkeyPatch):
    # git missing, gh present
    results = [
        DependencyInfo(name="git", installed=False),
        DependencyInfo(name="gh", installed=True, version="gh version 2.0.0", path="/usr/bin/gh"),
        DependencyInfo(name="python", installed=True, version="3.11.9", path="/usr/bin/python"),
    ]

    monkeypatch.setattr("cocode.cli.doctor.check_all", lambda: results)
    monkeypatch.setattr("cocode.cli.doctor.discover_agents", lambda: [])
    monkeypatch.setattr("cocode.cli.doctor.get_auth_status", lambda: _fake_auth(True))

    with pytest.raises(typer.Exit) as ei:
        doctor_command()
    assert ei.value.exit_code == ExitCode.MISSING_DEPS


def test_doctor_success(monkeypatch: pytest.MonkeyPatch):
    results = [
        DependencyInfo(
            name="git", installed=True, version="git version 2.44.0", path="/usr/bin/git"
        ),
        DependencyInfo(name="gh", installed=True, version="gh version 2.45.0", path="/usr/bin/gh"),
        DependencyInfo(name="python", installed=True, version="3.11.9", path="/usr/bin/python"),
    ]
    monkeypatch.setattr("cocode.cli.doctor.check_all", lambda: results)
    monkeypatch.setattr("cocode.cli.doctor.discover_agents", lambda: [])
    monkeypatch.setattr("cocode.cli.doctor.get_auth_status", lambda: _fake_auth(True))

    with pytest.raises(typer.Exit) as ei:
        doctor_command()
    assert ei.value.exit_code == ExitCode.SUCCESS
