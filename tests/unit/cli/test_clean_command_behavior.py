"""Behavior tests for clean command with mocked WorktreeManager."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

import cocode.__main__ as main_mod
from cocode.cli.clean import WorktreeError
from cocode.utils.exit_codes import ExitCode


def test_clean_no_repo(monkeypatch: pytest.MonkeyPatch):
    class BoomManager:
        def __init__(self, *_: object, **__: object):
            raise WorktreeError("not a repo")

    monkeypatch.setattr("cocode.cli.clean.WorktreeManager", BoomManager)
    runner = CliRunner()
    result = runner.invoke(main_mod.app, ["clean"])  # handled by Typer
    assert result.exit_code == ExitCode.GENERAL_ERROR


def test_clean_no_worktrees(monkeypatch: pytest.MonkeyPatch):
    class EmptyManager:
        def __init__(self, *_: object, **__: object):
            pass

        def list_worktrees(self) -> list[Path]:
            return []

    monkeypatch.setattr("cocode.cli.clean.WorktreeManager", EmptyManager)
    runner = CliRunner()
    result = runner.invoke(main_mod.app, ["clean"])  # handled by Typer
    assert result.exit_code == ExitCode.SUCCESS


def test_clean_remove_all_noninteractive(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    removed: list[Path] = []

    class Manager:
        def __init__(self, *_: object, **__: object):
            pass

        def list_worktrees(self) -> list[Path]:
            return [tmp_path / "wt1", tmp_path / "wt2"]

        def get_worktree_info(self, path: Path) -> dict[str, object]:
            return {"branch": f"branch-{path.name}", "has_changes": False}

        def remove_worktree(self, path: Path) -> None:
            removed.append(path)

    monkeypatch.setattr("cocode.cli.clean.WorktreeManager", Manager)
    runner = CliRunner()
    result = runner.invoke(main_mod.app, ["clean", "--all", "--no-interactive", "--force"])  # type: ignore[list-item]
    assert result.exit_code == ExitCode.SUCCESS
    assert len(removed) == 2
