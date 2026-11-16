# this_file: tests/test_near_miss_dialog.py
"""Real standalone Qt panel refresh/recovery and all four visible close terminals."""

from module_paths import module_name as _module_name
import importlib
import os
import sys
from types import SimpleNamespace as S

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import fontlabapp.contours.near_miss.model as report
from PySide6 import QtCore, QtGui, QtWidgets
from shiboken6 import isValid

APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def panel(monkeypatch):
    class Dialog(QtWidgets.QDialog):
        palette = property(QtWidgets.QDialog.palette)

    class Label(QtWidgets.QLabel):
        font = property(QtWidgets.QLabel.font)

    gui = S(**{n: getattr(QtGui, n) for n in dir(QtGui) if n.startswith("Q")})
    gui.__dict__.update(
        {n: getattr(QtWidgets, n) for n in dir(QtWidgets) if n.startswith("Q")}
    )
    gui.QDialog = Dialog
    gui.QLabel = Label
    monkeypatch.setitem(sys.modules, "PythonQt", S(QtGui=gui, QtCore=QtCore))
    for name in ["_names_dialog", "_snapshot_text_dialog", "_near_miss_dialog"]:
        monkeypatch.delitem(sys.modules, _module_name(name), raising=False)
    module = importlib.import_module("fontlabapp.contours.near_miss.ui")
    state = S(fail=False, calls=0)

    def capture():
        state.calls += 1
        if state.fail:
            raise ValueError("owned stale source")
        return (
            report.Glyph("a", "Regular", "Regular", (800, 700, 500, -200), (), (), ()),
        )

    monkeypatch.setattr(module.native, "capture", capture)
    widget = module.NearMissDialog()
    widget.show()
    APP.processEvents()
    yield widget, state, module
    if isValid(widget):
        widget.close()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


@pytest.mark.parametrize("terminal", ["close", "escape", "button", "reject"])
def test_actual_owned_panel_refresh_failure_recovery_and_close(panel, terminal):
    widget, state, _module = panel
    assert widget.isVisible() and not widget.isModal() and widget.output.isReadOnly()
    assert "No near misses" in widget.output.toPlainText()
    assert "Strict near-angle" in widget.subtitle.text()
    assert "Native acceptance pending" not in widget.subtitle.text()
    widget.refresh_button.click()
    assert state.calls == 2
    state.fail = True
    widget.refresh_button.click()
    assert (
        widget.report is None
        and widget.output.toPlainText() == ""
        and "owned stale" in widget.status.text()
    )
    state.fail = False
    widget.refresh_button.click()
    assert widget.report
    if terminal == "close":
        widget.close()
    elif terminal == "escape":
        from PySide6.QtTest import QTest

        QTest.keyClick(widget, QtCore.Qt.Key_Escape)
    elif terminal == "button":
        widget.close_button.click()
    else:
        widget.reject()
    APP.processEvents()
    calls = state.calls
    widget.refresh()
    assert state.calls == calls
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert not isValid(widget)


def test_public_lazy_show_uses_shared_registry(panel, monkeypatch):
    widget, _state, module = panel
    calls = []
    from fontlabapp.core import scripting

    monkeypatch.setattr(
        scripting,
        "show_script_dialog",
        lambda cls, key: calls.append((cls, key)) or widget,
    )
    assert report.show() is widget and calls == [(module.NearMissDialog, "near_miss")]
