"""Unit tests for dependency checks."""

import sys

from cocode.utils import dependencies as deps


def test_check_python_matches_runtime():
    info = deps.check_python()
    assert info.name == "python"
    assert info.installed is True
    major_minor = f"{sys.version_info.major}.{sys.version_info.minor}"
    assert info.version is not None and info.version.startswith(major_minor)
    assert info.path and isinstance(info.path, str)


def test_check_git_structure():
    info = deps.check_git()
    # Git is used in test fixtures; usually present, but don't assert True.
    assert info.name == "git"
    assert isinstance(info.installed, bool)
    # If installed, we should have a non-empty version and path
    if info.installed:
        assert info.version and isinstance(info.version, str)
        assert info.path and isinstance(info.path, str)


def test_check_gh_structure():
    info = deps.check_gh()
    assert info.name == "gh"
    assert isinstance(info.installed, bool)
    if info.installed:
        assert info.version and isinstance(info.version, str)
        assert info.path and isinstance(info.path, str)


def test_check_all_contains_expected_names():
    names = {i.name for i in deps.check_all()}
    assert {"git", "gh", "python"}.issubset(names)
