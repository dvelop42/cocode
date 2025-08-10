"""Minimal tests for the Textual app stub."""

from cocode.tui.app import CocodeApp


def test_cocode_app_instantiation():
    app = CocodeApp()
    assert hasattr(app, "on_mount")


def test_cocode_app_on_mount_noop():
    app = CocodeApp()
    # Should not raise
    app.on_mount()
