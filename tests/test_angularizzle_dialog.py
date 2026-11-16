# this_file: tests/test_angularizzle_dialog.py
"""Exercise owned real widgets with injected fonts/preferences, outside FontLab."""

import importlib
import os
import sys
from types import SimpleNamespace as NS

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PySide6 import QtCore, QtGui, QtWidgets
from shiboken6 import isValid
from test_angularizzle_session import OwnedBackend, layer

APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def tool(monkeypatch):
    class Dialog(QtWidgets.QDialog):
        geometry = property(QtWidgets.QDialog.geometry)

        def __setattr__(self, name, value):
            assert QtWidgets.QDialog.staticMetaObject.indexOfProperty(name) < 0
            assert not callable(getattr(QtWidgets.QDialog, name, None))
            super().__setattr__(name, value)

    class Edit(QtWidgets.QLineEdit):
        text = property(QtWidgets.QLineEdit.text)

    gui = NS(
        **{name: getattr(QtGui, name) for name in dir(QtGui) if name.startswith("Q")}
    )
    gui.__dict__.update(
        {
            name: getattr(QtWidgets, name)
            for name in dir(QtWidgets)
            if name.startswith("Q")
        }
    )
    gui.QDialog, gui.QLineEdit = Dialog, Edit
    monkeypatch.setitem(sys.modules, "PythonQt", NS(QtCore=QtCore, QtGui=gui))
    monkeypatch.delitem(sys.modules, "fontlabapp.contours.angularizzle.ui", raising=False)
    module = importlib.import_module("fontlabapp.contours.angularizzle.ui")
    backend, preferences = OwnedBackend((layer(),)), {}
    widget = module.AngularizzleDialog(backend=backend, preferences=preferences)
    yield widget, backend, preferences, module
    if isValid(widget):
        widget.close()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_original_controls_defaults_and_single_process_cancel_are_live(tool):
    widget, backend, values, mod = tool
    assert widget.windowTitle() == "Angularizzle Yo" and not widget.isModal()
    assert widget.plane_input.text == "80" and widget.detail_input.isChecked()
    assert (
        widget.process_button.text() == "Process" and widget.process_button.isDefault()
    )
    widget.process_button.click()
    assert not widget._closed and backend.current["A"].paths != layer().paths
    assert values[mod.prefs.PLANE] == "80" and values[mod.prefs.CHECK] is True
    widget.cancel_button.click()
    assert widget._closed and backend.current["A"].paths == layer().paths


def test_invalid_input_or_write_error_keeps_diagnosed_closable_original_panel(tool):
    widget, backend, _, _ = tool
    widget.plane_input.setText("invalid")
    widget.process_button.click()
    assert "plane" in widget.status.text() and not widget._closed
    assert backend.current["A"] == layer()
    widget.plane_input.setText("80")
    backend.failure = True
    widget.process_button.click()
    assert "refused" in widget.status.text() and widget.cancel_button.isEnabled()
    assert not widget._closed


def test_missing_source_does_not_prevent_closing_and_never_creates_a_fake_preview(tool):
    _, _, _, mod = tool
    widget = mod.AngularizzleDialog(backend=OwnedBackend(()), preferences={})
    assert widget.session is None and not widget.process_button.isEnabled()
    assert "Select" in widget.status.text()
    widget.cancel_button.click()
    assert widget._closed


def test_batch_process_closes_and_defaults_and_window_placement_reopen(tool):
    _, _, _, mod = tool
    values = {
        mod.prefs.PLANE: "40",
        mod.prefs.LEGACY_CHECK: False,
        mod.prefs.WINDOW: (10, 20, 360, 200),
    }
    widget = mod.AngularizzleDialog(
        backend=OwnedBackend((layer("A"), layer("B"))), preferences=values
    )
    assert widget.plane_input.text == "40" and not widget.detail_input.isChecked()
    widget.process_button.click()
    assert widget._closed and values[mod.prefs.CHECK] is False
    assert len(values[mod.prefs.WINDOW]) == 4


@pytest.mark.parametrize("route", ["close", "direct", "parent", "done"])
def test_saved_callbacks_are_inert_after_all_close_and_destruction_routes(
    tool, monkeypatch, route
):
    _, _, _, mod = tool
    parent = QtWidgets.QWidget()
    backend = OwnedBackend((layer(),))
    widget = mod.AngularizzleDialog(parent, backend=backend, preferences={})
    callbacks = [slot for _, slot in widget._connections[:2]]
    if route == "close":
        widget.close()
    elif route == "done":
        widget.done(0)
    else:
        (parent if route == "parent" else widget).deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    calls = tuple(backend.calls)
    with monkeypatch.context() as patch:
        patch.setattr(
            mod.AngularizzleDialog,
            "close",
            lambda self: pytest.fail("Deleted native close was touched"),
        )
        for callback in callbacks:
            callback()
    assert widget._closed and not widget._connections and tuple(backend.calls) == calls
    if isValid(parent):
        parent.deleteLater()


def test_poisoned_writer_is_disabled_and_retained_after_close_for_recovery(tool):
    widget, backend, _, _ = tool

    def fail(*args, **kwargs):
        backend.poisoned = True
        raise RuntimeError("Partial native failure; manual recovery required")

    backend.apply = fail
    widget.process_button.click()
    assert "Partial" in widget.status.text()
    assert (
        not widget.process_button.isEnabled() and not widget.cancel_button.isEnabled()
    )
    widget.close()
    assert backend in sys._fontlab_angularizzle_recovery


def test_settings_failure_reports_processed_result_without_reverting_font(
    tool, monkeypatch
):
    widget, backend, _, mod = tool

    def refused(*args):
        raise OSError("owned settings unavailable")

    monkeypatch.setattr(mod.prefs, "save", refused)
    widget.process_button.click()
    assert backend.current["A"].paths != layer().paths
    assert "Processed; settings were not saved" in widget.status.text()
    assert widget.persistence_error == "owned settings unavailable"


def test_cancel_failure_stays_open_and_close_diagnoses_disconnect_failure(tool):
    widget, backend, _, _ = tool
    widget.process()
    backend.failure = True
    widget.cancel()
    assert not widget._closed and "refused" in widget.status.text()

    class BrokenSignal:
        def disconnect(self, callback):
            raise RuntimeError("owned disconnect failed")

    widget._connections.append((BrokenSignal(), lambda: None))
    widget.close()
    assert widget._closed and any(
        "owned disconnect failed" in e for e in widget.cleanup_errors
    )
