# this_file: tests/test_clean_classes_panel.py
"""Actual owned Qt write controls and shared completion lifecycle."""

from module_paths import module_name as _module_name
import importlib
import os
import sys
from types import SimpleNamespace as NS

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PySide6 import QtCore, QtGui, QtWidgets
from shiboken6 import isValid
from fontlabapp.features.classes.model import Snapshot

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
    for name in ("_names_dialog", "_snapshot_text_dialog"):
        monkeypatch.delitem(sys.modules, _module_name(name), raising=False)
    module = importlib.import_module("fontlabapp.features.classes.ui")

    class Bridge:
        poisoned = False

        def __init__(self):
            self.facts = Snapshot((1,), ("A",), (("caps", " A gone A "),))
            self.mode = "ok"
            self.writes = []

        def capture(self, *, deadline=None):
            if self.mode == "capture":
                raise ValueError("capture failed")
            return self.facts

        def begin(self):
            pass

        def write(self, name, members):
            if self.mode == "partial":
                raise RuntimeError("native failure")
            self.writes.append((name, members))
            self.facts = Snapshot((1,), ("A",), (("caps", "A A"),))
            if self.mode == "post":
                self.mode = "capture"

        def end(self):
            pass

    b = Bridge()
    w = module.panel_type(QtCore, gui)(None, b)
    yield w, b
    if isValid(w):
        w.close()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_complete_preview_apply_rescan_noop_and_closed_calls(panel):
    w, b = panel
    assert (
        w.apply_button.isEnabled()
        and w.output.isReadOnly()
        and "gone" in w.output.toPlainText()
    )
    w.apply_button.click()
    assert b.writes == [("caps", ("A", "A"))] and not w.apply_button.isEnabled()
    assert w.status.text() == "Cleaned 1 classes; removed 1 missing names."
    w.busy = True
    w.refresh()
    w.apply()
    w.busy = False
    w.close()
    w.refresh()
    w.apply()
    assert w.bridge is None


@pytest.mark.parametrize("mode", ["partial", "post", "capture"])
def test_errors_clear_actionable_preview_and_keep_diagnosis(panel, mode):
    w, b = panel
    b.mode = mode
    (w.refresh_button if mode == "capture" else w.apply_button).click()
    assert (
        w.report is None
        and not w.apply_button.isEnabled()
        and not w.output.toPlainText()
    )
    assert ("Undo" if mode != "capture" else "capture failed") in w.status.text()


@pytest.mark.parametrize(
    "route", ["close", "accept", "reject", "done", "escape", "destroy"]
)
def test_completion_releases_backend_registry_and_late_callbacks(panel, route):
    w, b = panel
    sys.__dict__.setdefault("_fontlab_samples", {})[w.KEY] = w
    w.show()
    if route == "done":
        w.done(42)
    elif route == "destroy":
        w.deleteLater()
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    elif route == "escape":
        w.keyPressEvent(
            QtGui.QKeyEvent(
                QtCore.QEvent.KeyPress, QtCore.Qt.Key_Escape, QtCore.Qt.NoModifier
            )
        )
    else:
        getattr(w, route)()
    assert w._closed and w.bridge is None and w.report is None
    assert sys._fontlab_samples.get(w.KEY) is not w
    w.refresh()
    w.apply()
