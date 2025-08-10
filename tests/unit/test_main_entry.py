"""Tests for cocode.__main__ entry behavior."""

from __future__ import annotations

import pytest
import typer

import cocode.__main__ as main_mod


def test_global_version_option_triggers_exit():
    # Create a mock context using the Mock library
    from unittest.mock import Mock

    ctx = Mock()
    ctx.ensure_object.return_value = None
    ctx.obj = {}

    with pytest.raises(typer.Exit) as ei:
        main_mod._global_options(ctx, version=True, log_level="INFO", dry_run=False)
    # click Exit uses code 0 for normal termination
    assert ei.value.exit_code in (None, 0)


def test_main_keyboard_interrupt(monkeypatch):
    monkeypatch.setattr(main_mod, "app", lambda: (_ for _ in ()).throw(KeyboardInterrupt()))
    assert main_mod.main() == 130


def test_main_generic_exception(monkeypatch):
    monkeypatch.setattr(main_mod, "app", lambda: (_ for _ in ()).throw(Exception("boom")))
    assert main_mod.main() == 1


def test_global_dry_run_env_normalization_false(monkeypatch):
    """COCODE_DRY_RUN env like '0' should override flag to False."""
    from unittest.mock import Mock

    monkeypatch.setenv("COCODE_DRY_RUN", "0")

    ctx = Mock()
    ctx.ensure_object.return_value = None
    ctx.obj = {}

    # Pass dry_run=True, but env should normalize it to False
    main_mod._global_options(ctx, version=False, log_level="INFO", dry_run=True)
    assert ctx.obj.get("dry_run") is False


def test_main_success_returns_zero(monkeypatch):
    """When app runs normally, main returns 0."""
    called = {}

    def fake_app():
        called["ok"] = True

    monkeypatch.setattr(main_mod, "app", fake_app)
    assert main_mod.main() == 0
    assert called.get("ok") is True
