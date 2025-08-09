import subprocess
from types import SimpleNamespace

from cocode.github.auth import get_auth_status


class _DummyProc(SimpleNamespace):
    pass


def _make_proc(stdout: str = "", stderr: str = "", returncode: int = 0):
    return _DummyProc(stdout=stdout, stderr=stderr, returncode=returncode)


def test_auth_status_parses_logged_in(monkeypatch):
    sample = (
        "github.com\n"
        "  ✓ Logged in to github.com as alice (oauth_token)\n"
        "  ✓ Git operations for github.com configured to use https protocol.\n"
        "  ✓ Token: *******************\n"
    )

    def fake_run(*args, **kwargs):  # type: ignore[no-redef]
        return _make_proc(stdout=sample, stderr="", returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    status = get_auth_status()

    assert status.authenticated is True
    assert status.host == "github.com"
    assert status.username == "alice"
    assert status.auth_method == "oauth_token"
    assert status.error is None


def test_auth_status_not_logged_in(monkeypatch):
    stderr = "You are not logged into any GitHub hosts. Run gh auth login.\n"

    def fake_run(*args, **kwargs):  # type: ignore[no-redef]
        return _make_proc(stdout="", stderr=stderr, returncode=1)

    monkeypatch.setattr(subprocess, "run", fake_run)
    status = get_auth_status()

    assert status.authenticated is False
    assert status.username is None
    assert status.error is not None


def test_auth_status_gh_missing(monkeypatch):
    def fake_run(*args, **kwargs):  # type: ignore[no-redef]
        raise FileNotFoundError("gh not found")

    monkeypatch.setattr(subprocess, "run", fake_run)
    status = get_auth_status()

    assert status.authenticated is False
    assert status.error is not None


def test_auth_status_authenticated_but_unparsed(monkeypatch):
    # Simulate a successful return without the expected "Logged in to ..." line
    sample = "github.com\n" "  ✓ Token: *******************\n" "  ✓ Git operations configured.\n"

    def fake_run(*args, **kwargs):  # type: ignore[no-redef]
        return _make_proc(stdout=sample, stderr="", returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    status = get_auth_status()

    assert status.authenticated is True
    # Details are unknown in fallback; ensure fields are None
    assert status.username is None
    assert status.host is None
    assert status.auth_method is None
