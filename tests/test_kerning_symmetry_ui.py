# this_file: tests/test_kerning_symmetry_ui.py
"""Complete operation into the existing real Qt result/lifetime surface."""

import sys

import fontlabapp.kerning.symmetry.model as model
import pytest
from fontlabapp.core import scripting
from test_kerning_symmetry_native import fixture
from test_reports import report_ui as shared_report_ui

report_ui = shared_report_ui


def combined_fixture(monkeypatch, report_ui):
    qt = scripting._native("PythonQt")
    values = fixture(monkeypatch)
    host = scripting._native("fontlab")
    host.MainWindow = lambda: report_ui[1]
    monkeypatch.setattr(
        scripting, "_native", lambda name: qt if name == "PythonQt" else host
    )
    return values


@pytest.mark.parametrize("terminal", ["button", "close", "reject", "parent"])
def test_actual_result_lifetime_does_not_repeat_writer(
    report_ui, monkeypatch, terminal
):
    _mod, parent, core = report_ui
    _font, _kerns, history, _state, _names = combined_fixture(monkeypatch, report_ui)
    panel = model.show()
    assert panel.report["applied"] and panel.editor.isReadOnly()
    assert "requested_value" in panel.editor.toPlainText()
    assert len(history) == 2
    callbacks = [slot for _, slot in panel._connections]
    if terminal == "parent":
        parent.deleteLater()
    elif terminal == "button":
        panel.close_button.click()
    elif terminal == "reject":
        panel.reject()
    else:
        panel.close()
    core.QCoreApplication.sendPostedEvents(None, core.QEvent.DeferredDelete)
    assert (
        panel._released
        and not panel._connections
        and model.KEY not in sys._fontlab_samples
    )
    for callback in callbacks:
        callback()
    assert len(history) == 2


def test_relaunch_replaces_only_owned_result_and_noop_has_no_extra_history(
    report_ui, monkeypatch
):
    combined_fixture(monkeypatch, report_ui)
    first = model.show()
    second = model.show()
    assert first._released and not second.report["applied"]
    assert sys._fontlab_samples[model.KEY] is second


def test_error_no_font_uses_actual_closable_result(report_ui, monkeypatch):
    _, _, history, state, _ = combined_fixture(monkeypatch, report_ui)
    state.package = None
    panel = model.show()
    assert "font" in panel.report["error"] and not history
    panel.close_button.click()
    assert panel._released
