# this_file: tests/test_tabular_width_dialog.py
"""Exercise actual adapted widgets offscreen; never run reference bodies."""

import importlib
import os
import sys
from types import SimpleNamespace as NS

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PySide6 import QtCore, QtGui, QtWidgets
from shiboken6 import isValid

APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def panel(monkeypatch):
    class Dialog(QtWidgets.QDialog):
        palette = property(QtWidgets.QDialog.palette)

        def __setattr__(self, name, value):
            assert QtWidgets.QDialog.staticMetaObject.indexOfProperty(name) < 0
            assert not callable(getattr(QtWidgets.QDialog, name, None))
            super().__setattr__(name, value)

    class Label(QtWidgets.QLabel):
        font = property(QtWidgets.QLabel.font)

    gui = NS(**{n: getattr(QtGui, n) for n in dir(QtGui) if n.startswith("Q")})
    gui.__dict__.update(
        {n: getattr(QtWidgets, n) for n in dir(QtWidgets) if n.startswith("Q")}
    )
    gui.QDialog, gui.QLabel = Dialog, Label
    monkeypatch.setitem(sys.modules, "PythonQt", NS(QtCore=QtCore, QtGui=gui))
    for name in ("fontlabapp.glyphs.names.ui", "fontlabapp.metrics.tabular_width.ui"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    mod = importlib.import_module("fontlabapp.metrics.tabular_width.ui")
    report = mod.api.compare((("A", 500.125), ("B", 500.126)), "12:34:56")
    monkeypatch.setattr(mod.api, "capture", lambda: report)
    widget = mod.TabularWidthDialog()
    yield widget, mod
    if isValid(widget):
        widget.close()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_complete_initial_report_refresh_failure_and_recovery(panel, monkeypatch):
    widget, mod = panel
    assert widget.output.isReadOnly() and not widget.isModal()
    assert "500.126" in widget.output.toPlainText()
    assert widget.report.same == 1 and widget.report.different == 1
    original = mod.api.capture

    def fail():
        raise ValueError("injected read failure")

    monkeypatch.setattr(mod.api, "capture", fail)
    widget.refresh_button.click()
    assert widget.report is None and widget.output.toPlainText() == ""
    assert "injected" in widget.status.text()
    monkeypatch.setattr(mod.api, "capture", original)
    widget.refresh()
    assert widget.report.same == 1


def test_initial_failure_has_close_and_closed_refresh_is_fenced(panel, monkeypatch):
    _, mod = panel
    monkeypatch.setattr(
        mod.api, "capture", lambda: (_ for _ in ()).throw(ValueError("No font"))
    )
    widget = mod.TabularWidthDialog()
    assert widget.report is None and widget.close_button.isEnabled()
    widget.close_button.click()
    assert widget._closed and not widget._connections
    widget.refresh()


@pytest.mark.parametrize("owner", ["parent", "direct"])
def test_destruction_releases_every_owned_slot(panel, owner):
    _, mod = panel
    parent = QtWidgets.QWidget()
    widget = mod.TabularWidthDialog(parent)
    assert widget._connections
    (parent if owner == "parent" else widget).deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert widget._closed and not widget._connections and not widget._disconnect_errors
    if isValid(parent):
        parent.deleteLater()


def test_factory_and_repeat_launch_use_existing_owned_registry(panel, monkeypatch):
    first, mod = panel
    import fontlabapp.core.scripting as scripting

    monkeypatch.setitem(sys.modules, "fontlab", NS(MainWindow=lambda: None))
    assert scripting.tabular_width_dialog_type() is mod.TabularWidthDialog
    second = scripting.show_script_dialog(
        mod.TabularWidthDialog, mod.TabularWidthDialog.KEY
    )
    third = scripting.show_script_dialog(
        mod.TabularWidthDialog, mod.TabularWidthDialog.KEY
    )
    assert second._closed and not second._connections
    third.close()


def test_disconnect_error_retained_during_destroy(panel):
    widget, _ = panel

    class Failure:
        def disconnect(self, slot):
            raise RuntimeError("disconnect fault")

    widget._connections.append((Failure(), lambda: None))
    widget._destroyed()
    assert widget._disconnect_errors == ["RuntimeError('disconnect fault')"]
    widget.close()


@pytest.mark.parametrize("ending", ["close", "direct", "parent"])
def test_retained_close_callback_is_inert_after_release(panel, ending):
    """A queued callback must never call a released native wrapper."""
    _, mod = panel
    parent = QtWidgets.QWidget()
    widget = mod.TabularWidthDialog(parent)
    close_callback = next(
        slot
        for signal, slot in widget._connections
        if signal == widget.close_button.clicked
    )
    if ending == "close":
        widget.close()
    else:
        (widget if ending == "direct" else parent).deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert not isValid(widget), "The callback must be tested against a deleted wrapper"
    close_callback()
    if isValid(parent):
        parent.deleteLater()


def test_deadline_failure_clears_previous_report_and_keeps_close(panel, monkeypatch):
    widget, mod = panel
    assert widget.report is not None

    def timeout():
        raise TimeoutError("Selection scan exceeded its deadline; no partial report.")

    monkeypatch.setattr(mod.api, "capture", timeout)
    widget.refresh_button.click()
    assert widget.report is None and widget.output.toPlainText() == ""
    assert "deadline" in widget.status.text() and widget.close_button.isEnabled()
