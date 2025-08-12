"""Tests for cocode.utils.validation functions."""

from pathlib import Path

import pytest

from cocode.utils.validation import (
    sanitize_branch_name,
    validate_agent_path,
    validate_issue_number,
    validate_repo_path,
)


def test_validate_issue_number():
    assert validate_issue_number(1) is True
    assert validate_issue_number(9999) is True
    assert validate_issue_number(0) is False
    assert validate_issue_number(-5) is False
    # Booleans should be rejected even though bool is subclass of int
    assert validate_issue_number(True) is False  # type: ignore[arg-type]
    assert validate_issue_number(False) is False  # type: ignore[arg-type]
    # non-int values should be False
    assert validate_issue_number("3") is False  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("feature/new-thing", "feature/new-thing"),
        (" Feature: New Thing! ", "Feature-New-Thing"),
        ("...strange..name...", "strange-name"),
        ("--bad__chars??--", "bad__chars"),
        ("", "branch"),
    ],
)
def test_sanitize_branch_name(raw: str, expected: str):
    assert sanitize_branch_name(raw) == expected


def test_validate_agent_path_within_worktree(tmp_path: Path):
    root = tmp_path / "worktree"
    nested = root / "a" / "b"
    nested.mkdir(parents=True)
    assert validate_agent_path(nested, root) is True


def test_validate_agent_path_outside_worktree(tmp_path: Path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    assert validate_agent_path(outside, root) is False


def test_validate_repo_path(tmp_path: Path):
    # missing .git
    assert validate_repo_path(tmp_path) is False

    # .git directory
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    assert validate_repo_path(tmp_path) is True

    # .git file (e.g., gitlink/worktree case)
    file_repo = tmp_path / "file-repo"
    file_repo.mkdir()
    git_file = file_repo / ".git"
    git_file.write_text("gitdir: /some/other/path\n")
    assert validate_repo_path(file_repo) is True
