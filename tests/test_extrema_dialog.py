# this_file: tests/test_extrema_dialog.py
"""Actual owned report panel; coordinate retention plus required proof actions."""

from module_paths import module_name as _module_name
import importlib
import os
import sys
from types import SimpleNamespace as NS

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PySide6 import QtCore, QtGui, QtWidgets
from shiboken6 import isValid

from fontlabapp.proof.extrema.model import ProofError
from fontlabapp.masters.layers.extrema.model import Extremes, LayerExtent

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
    for name in ("_names_dialog", "_snapshot_text_dialog", "_extrema_dialog"):
        monkeypatch.delitem(sys.modules, _module_name(name), raising=False)
    mod = importlib.import_module("fontlabapp.proof.extrema.ui")
    state = NS(calls=[], fail=None)
    result = Extremes(
        LayerExtent("A.alt", "Bold", -10.25, 700.5),
        LayerExtent("g", "Sketch", -250.125, 500.0),
    )

    def run(mode):
        state.calls.append(mode)
        if state.fail == "tab":
            raise ProofError(result, ValueError("owned populate failure"))
        if state.fail == "read":
            raise ValueError("source changed")
        return result

    monkeypatch.setattr(mod, "run", run)
    widget = mod.ExtremaDialog()
    yield widget, mod, state, result
    if isValid(widget):
        widget.close()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_coordinate_report_runs_the_required_proof_on_launch_and_repeat(panel):
    w, _, state, _ = panel
    assert state.calls == ["all"] and w.output.isReadOnly()
    assert w.output.toPlainText().startswith("highest: 700.5\nlowest: -250.125")
    assert "A.alt [Bold]" in w.output.toPlainText()
    assert w.refresh_button.text() == "Run Again"
    w.refresh_button.click()
    assert state.calls == ["all", "all"]


def test_failed_tab_keeps_coordinates_but_failed_read_clears_stale_report(panel):
    w, _, state, result = panel
    state.fail = "tab"
    w.refresh_button.click()
    assert w.report[0] == result and "owned populate failure" in w.status.text()
    assert "700.5" in w.output.toPlainText()
    state.fail = "read"
    w.refresh_button.click()
    assert w.report is None and w.output.toPlainText() == ""
    assert "source changed" in w.status.text()


@pytest.mark.parametrize(
    "route", ["close", "reject", "accept", "done", "escape", "destroy"]
)
def test_all_terminal_routes_release_captures_and_owned_registry(panel, route):
    w, _, state, _ = panel
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
    count = len(state.calls)
    w.refresh()
    assert len(state.calls) == count
