# this_file: tests/test_text_filter_failures.py
"""Fault and late-callback controls for the actual owned Text Filter panel."""

import pytest
from test_text_filter_dialog import QtCore, panel as shared_panel


@pytest.fixture
def panel(monkeypatch, tmp_path):
    yield from shared_panel.__wrapped__(monkeypatch, tmp_path)


def test_default_settings_are_in_tool_namespace_and_fontless_filter_still_works(
    panel, monkeypatch, tmp_path
):
    _, mod, settings, _ = panel
    Settings = type(settings)
    calls = []

    def factory(*args):
        calls.append(args)
        return Settings(str(tmp_path / "default.ini"), Settings.IniFormat)

    monkeypatch.setattr(mod.QtCore, "QSettings", factory)
    monkeypatch.setattr(mod, "current_package", lambda: None)
    w = mod.TextFilterDialog()
    try:
        assert calls == [("FontLab", "ScriptTextFilter")]
        assert w._settings.fallbacksEnabled() is False
        w.input_edit.setPlainText("a1")
        w.characters_edit.setPlainText("a-z")
        w.new_tab.setChecked(True)
        w.simplify_button.click()
        assert w.output_edit.toPlainText() == "a" and "with a font" in w.status.text()
    finally:
        w.close()


@pytest.mark.parametrize("fault", ["input", "geometry"])
def test_corrupt_saved_state_is_diagnosed_without_initial_overwrite(panel, fault):
    _, mod, settings, _ = panel
    value = 42 if fault == "input" else QtCore.QByteArray(b"broken")
    settings.setValue(fault, value)
    w = mod.TextFilterDialog(settings=settings)
    try:
        assert "could not be loaded" in w.status.text()
        assert settings.value(fault) == value
        w.input_edit.setPlainText("repaired")
        w.simplify_button.click()
        assert not w.settings_error
    finally:
        w.close()


def test_failed_autosave_keeps_text_and_does_not_claim_saved_success(
    panel, monkeypatch
):
    w, mod, _, _ = panel

    def fail(*args):
        raise OSError("owned store failure")

    monkeypatch.setattr(mod.prefs, "save", fail)
    w.input_edit.setPlainText("A1")
    w.simplify_button.click()
    assert w.output_edit.toPlainText() == "A"
    assert "not saved" in w.status.text() and "failure" in w.settings_error
    monkeypatch.setattr(mod.prefs, "reset", fail)
    w.reset_button.click()
    assert w.output_edit.toPlainText() == "A" and "failure" in w.status.text()
    monkeypatch.setattr(mod.prefs, "sync", fail)
    w.close()
    assert w._closed and "owned store failure" in w.slot_error


def test_reentrant_simplify_does_not_open_two_tabs(panel):
    w, _, _, _ = panel
    calls = []
    w.input_edit.setPlainText("A1")
    w.new_tab.setChecked(True)

    def open_tab(text):
        calls.append(text)
        w.simplify()
        w.reset()

    w._open_tab = open_tab
    w.simplify_button.click()
    assert calls == ["A"]


def test_late_tab_error_after_destruction_does_not_touch_widgets(panel):
    w, _, _, _ = panel
    w.input_edit.setPlainText("A1")
    w.new_tab.setChecked(True)

    def late(text):
        w.close()
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        raise ValueError("late tab failure")

    w._open_tab = late
    callback = w._connections[-3][1]
    callback()
    assert w._closed and "late tab failure" in w.slot_error
    w.save()
    w.reset()
    w.simplify()


def test_output_autosave_closing_panel_stops_before_checkbox_and_tab(
    panel, monkeypatch
):
    w, mod, _, calls = panel
    w.input_edit.setPlainText("A1")
    w.new_tab.setChecked(True)
    monkeypatch.setattr(mod.prefs, "save", lambda *args: w.close())
    w.simplify_button.click()
    assert w._closed and calls == []


def test_late_autosave_error_after_close_keeps_only_error_data(panel, monkeypatch):
    w, mod, _, _ = panel

    def fail(*args):
        w.close()
        raise OSError("late save failure")

    monkeypatch.setattr(mod.prefs, "save", fail)
    w.input_edit.setPlainText("A1")
    assert w._closed and w._settings is None
    assert w.settings_error == "late save failure"
