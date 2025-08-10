"""Tests for cocode.__main__ entry behavior."""

from __future__ import annotations

import pytest
import typer

import cocode.__main__ as main_mod


def test_global_version_option_triggers_exit():
    with pytest.raises(typer.Exit) as ei:
        main_mod._global_options(version=True, log_level="INFO")
    # click Exit uses code 0 for normal termination
    assert ei.value.exit_code in (None, 0)


def test_main_keyboard_interrupt(monkeypatch):
    monkeypatch.setattr(main_mod, "app", lambda: (_ for _ in ()).throw(KeyboardInterrupt()))
    assert main_mod.main() == 130


def test_main_generic_exception(monkeypatch):
    monkeypatch.setattr(main_mod, "app", lambda: (_ for _ in ()).throw(Exception("boom")))
    assert main_mod.main() == 1
