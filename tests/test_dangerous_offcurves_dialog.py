# this_file: tests/test_dangerous_offcurves_dialog.py
"""Actual Qt controls for the complete plain report window and owned terminals."""

import os
import sys
from types import SimpleNamespace as NS

import pytest

if os.environ.get("FONTLABAPP_TEST_QT5") == "1":
    from PyQt5 import QtCore as C, QtGui as G, QtWidgets as W
else:
    from PySide6 import QtCore as C, QtGui as G, QtWidgets as W
import fontlabapp.contours.dangerous_offcurves.ui as ui
import fontlabapp.contours.dangerous_offcurves.model as model
import fontlabapp.contours.dangerous_offcurves.native as api
from fontlabapp.core import scripting


class Gui:
    QCloseEvent = G.QCloseEvent

    def __getattr__(self, name):
        return getattr(W, name)


QT = NS(QtCore=C, QtGui=Gui())


@pytest.fixture
def widget(monkeypatch):
    app = W.QApplication.instance() or W.QApplication([])
    monkeypatch.setattr(
        scripting,
        "_native",
        lambda n: QT if n == "PythonQt" else NS(MainWindow=lambda: None),
    )
    monkeypatch.setattr(ui, "_native", lambda n: QT)
    monkeypatch.setattr(sys.modules["fontlabapp"], "_native", lambda n: QT)
    monkeypatch.setattr(
        api, "run", lambda: model.Report(((1, 2),), (("A", "Bold"),), 0.05)
    )
    monkeypatch.setattr(sys, "_fontlab_samples", {}, raising=False)
    dialog = model.show()
    yield dialog, app
    if not dialog._closed:
        dialog.close()
    C.QCoreApplication.sendPostedEvents(None, C.QEvent.DeferredDelete)


def test_original_normal_fixed_window_and_readonly_full_text(widget):
    dialog, app = widget
    app.processEvents()
    assert dialog.windowTitle() == "Dangerous Offcurves" and not dialog.isModal()
    assert (dialog.width(), dialog.height()) == (620, 480)
    assert dialog.minimumSize() != dialog.maximumSize()
    assert dialog.windowFlags() & C.Qt.WindowType_Mask == C.Qt.Window
    assert dialog.windowFlags() & C.Qt.WindowStaysOnTopHint, (
        "Menu launcher preserves report chrome and adds TypeRig priority"
    )
    assert dialog.output.isReadOnly()
    assert dialog.output.toPlainText() == "A -- Bold\n"
    rect = dialog.output.geometry()
    assert (rect.x(), rect.y(), rect.width(), rect.height()) == (10, 10, 600, 460)
    dialog.output.selectAll()
    assert dialog.output.textCursor().hasSelection()


@pytest.mark.parametrize("terminal", ["close", "reject", "escape", "done"])
def test_all_native_terminals_destroy_only_owned_dialog_and_remove_registry(
    widget, terminal
):
    dialog, app = widget
    destroyed = []
    dialog.destroyed.connect(lambda *a: destroyed.append(True))
    if terminal == "escape":
        app.sendEvent(
            dialog, G.QKeyEvent(C.QEvent.KeyPress, C.Qt.Key_Escape, C.Qt.NoModifier)
        )
    elif terminal == "done":
        dialog.done(W.QDialog.Accepted)
    else:
        getattr(dialog, terminal)()
    C.QCoreApplication.sendPostedEvents(None, C.QEvent.DeferredDelete)
    assert destroyed == [True] and model.KEY not in sys._fontlab_samples
    assert dialog._completion_lifetime.closed and not dialog._completion_lifetime.hooks


def test_repeated_public_launch_closes_previous_snapshot(widget):
    first, _app = widget
    destroyed = []
    first.destroyed.connect(lambda *a: destroyed.append(True))
    second = model.show()
    assert second is not first and sys._fontlab_samples[model.KEY] is second
    second.close()
    C.QCoreApplication.sendPostedEvents(None, C.QEvent.DeferredDelete)
    assert destroyed == [True]


def test_empty_report_still_opens_readonly_window(monkeypatch, widget):
    _old, _app = widget
    monkeypatch.setattr(api, "run", lambda: model.Report((), (), 0.05))
    new = model.show()
    assert "Could not find any offcurve" in new.output.toPlainText()
    new.close()


def test_capture_failure_prevents_new_window_and_registry(monkeypatch, widget):
    old, _app = widget
    old.close()

    def fail():
        raise ValueError("owned failure")

    monkeypatch.setattr(api, "run", fail)
    with pytest.raises(ValueError, match="owned failure"):
        model.show()
    assert model.KEY not in sys._fontlab_samples


def test_parent_destruction_clears_owned_completion_registry(widget):
    old, _app = widget
    old.close()
    parent = W.QWidget()
    panel = ui.dialog_type(QT)(parent)
    sys._fontlab_samples[model.KEY] = panel
    parent.deleteLater()
    C.QCoreApplication.sendPostedEvents(None, C.QEvent.DeferredDelete)
    assert model.KEY not in sys._fontlab_samples and panel._completion_lifetime.closed


def test_late_rejection_after_owned_close_is_inert(widget):
    panel, _app = widget
    panel.close()
    panel.reject()
    assert panel._closed


def test_constructor_control_failure_releases_completion_before_deletion(
    monkeypatch, widget
):
    old, _app = widget
    old.close()
    created = []
    destroyed = []

    class Dialog(W.QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            created.append(self)
            self.destroyed.connect(lambda *a: destroyed.append(True))

    def fail(*args):
        raise RuntimeError("owned constructor fault")

    gui = Gui()
    gui.QDialog = Dialog
    gui.QPlainTextEdit = fail
    with pytest.raises(RuntimeError, match="owned constructor fault"):
        ui.dialog_type(NS(QtCore=C, QtGui=gui))()
    C.QCoreApplication.sendPostedEvents(None, C.QEvent.DeferredDelete)
    assert destroyed == [True] and created[0]._completion_lifetime.closed
