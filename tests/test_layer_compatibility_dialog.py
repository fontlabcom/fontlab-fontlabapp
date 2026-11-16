# this_file: tests/test_layer_compatibility_dialog.py
"""Actual owned compatibility report, complete Refresh/error/completion controls."""

from module_paths import module_name as _module_name
import importlib
import os
import sys
from types import SimpleNamespace as NS

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from fontlabapp.masters.layers.compatibility.model import GlyphLayers, Layer
from PySide6 import QtCore, QtGui, QtWidgets
from shiboken6 import isValid

APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def panel(monkeypatch):
    class Dialog(QtWidgets.QDialog):
        palette = property(QtWidgets.QDialog.palette)

    class Label(QtWidgets.QLabel):
        font = property(QtWidgets.QLabel.font)

    gui = NS(**{n: getattr(QtGui, n) for n in dir(QtGui) if n.startswith("Q")})
    gui.__dict__.update(
        {n: getattr(QtWidgets, n) for n in dir(QtWidgets) if n.startswith("Q")}
    )
    gui.QDialog, gui.QLabel = Dialog, Label
    monkeypatch.setitem(sys.modules, "PythonQt", NS(QtCore=QtCore, QtGui=gui))
    for name in (
        "_names_dialog",
        "_snapshot_text_dialog",
        "_layer_compatibility_dialog",
    ):
        monkeypatch.delitem(sys.modules, _module_name(name), raising=False)
    mod = importlib.import_module("fontlabapp.masters.layers.compatibility.ui")
    state = NS(calls=0, fail=False)
    report = (
        GlyphLayers(
            "A", (Layer("Regular", (("line",),)), Layer("Bold", (("curve",),)))
        ),
    )

    def capture():
        state.calls += 1
        if state.fail:
            raise ValueError("source changed")
        return report

    monkeypatch.setattr(mod.native, "capture", capture)
    w = mod.LayerCompatibilityDialog()
    yield w, mod, state
    if isValid(w):
        w.close()


def test_actual_report_when_refreshed_then_complete_text_status_and_errors(panel):
    w, _mod, state = panel
    assert not w.isModal() and w.output.isReadOnly()
    assert "A is not compatible" in w.output.toPlainText()
    assert (
        "Regular has line" in w.output.toPlainText()
        and "Bold has curve" in w.output.toPlainText()
    )
    assert "not an export-compatibility certificate" in w.subtitle.text()
    assert "1 selected occurrences" in w.status.text()
    w.refresh_button.click()
    assert state.calls == 2
    state.fail = True
    w.refresh_button.click()
    assert (
        w.report is None
        and not w.output.toPlainText()
        and "source changed" in w.status.text()
    )
    state.fail = False
    w.refresh_button.click()
    assert "A is not compatible" in w.output.toPlainText()


def test_public_show_when_called_then_shared_owned_registry(panel, monkeypatch):
    _w, mod, _state = panel
    from fontlabapp.core import scripting

    calls = []
    monkeypatch.setattr(
        scripting, "show_script_dialog", lambda cls, key: calls.append((cls, key))
    )
    mod.api.show()
    assert calls == [(mod.LayerCompatibilityDialog, "layer_compatibility")]


@pytest.mark.parametrize(
    "route", ["close", "reject", "accept", "done", "escape", "destroy"]
)
def test_terminal_routes_release_owned_report_and_late_refresh(panel, route):
    w, _mod, state = panel
    sys.__dict__.setdefault("_fontlab_samples", {})[w.KEY] = w
    w.show()
    if route == "close":
        w.close_button.click()
    elif route == "reject":
        w.reject()
    elif route == "accept":
        w.accept()
    elif route == "done":
        w.done(0)
    elif route == "destroy":
        w.deleteLater()
    else:
        from PySide6.QtTest import QTest

        QTest.keyClick(w, QtCore.Qt.Key_Escape)
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert w._closed and w.report is None and not w._connections
    assert w._capture is None and w._render is None and w._status is None
    assert w.KEY not in sys._fontlab_samples
    count = state.calls
    w.refresh()
    assert state.calls == count
