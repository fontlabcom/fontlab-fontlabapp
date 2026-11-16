# this_file: tests/test_bracket_layers_dialog.py
"""Actual owned Qt6 report panel, complete refresh/failure/completion lifecycle."""

from module_paths import module_name as _module_name
import importlib
import os
import sys
from types import SimpleNamespace as NS

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from fontlabapp.masters.layers.brackets.model import Glyph, analyse
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
    monkeypatch.setitem(sys.modules, "PythonQt", NS(QtGui=gui, QtCore=QtCore))
    for name in ["_names_dialog", "_snapshot_text_dialog", "_bracket_layers_dialog"]:
        monkeypatch.delitem(sys.modules, _module_name(name), raising=False)
    module = importlib.import_module("fontlabapp.masters.layers.brackets.ui")
    state = NS(calls=0, fail=False)
    result = analyse((Glyph("A", ("[100]",)), Glyph("B", (), frozenset({"A"}))))

    def capture():
        state.calls += 1
        if state.fail:
            raise ValueError("owned source changed")
        return result

    monkeypatch.setattr(module.native, "report", capture)
    widget = module.BracketLayersDialog()
    yield widget, module, state
    if isValid(widget):
        widget.close()


def test_panel_when_refreshed_then_original_groups_readonly_geometry_and_full_failure(
    panel,
):
    w, _, state = panel
    assert not w.isModal() and w.output.isReadOnly()
    assert (w.width(), w.height(), w.minimumWidth(), w.minimumHeight()) == (
        500,
        400,
        500,
        400,
    )
    assert "Glyphs with Bracket Layers (1):\nA" in w.output.toPlainText()
    assert "Affected Components (1):\nB" in w.output.toPlainText()
    assert "2" in w.status.text() and "current font" in w.subtitle.text()
    w.refresh_button.click()
    assert state.calls == 2
    state.fail = True
    w.refresh_button.click()
    assert (
        w.report is None
        and not w.output.toPlainText()
        and "owned source changed" in w.status.text()
    )
    state.fail = False
    w.refresh_button.click()
    assert "Total affected glyphs: 2" in w.output.toPlainText()


@pytest.mark.parametrize(
    "route", ["close", "reject", "accept", "done", "escape", "destroy"]
)
def test_panel_when_completed_then_disconnected_released_and_late_refresh_inert(
    panel, route
):
    w, _, state = panel
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
    previous = state.calls
    w.refresh()
    assert state.calls == previous
