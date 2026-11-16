# this_file: tests/test_canvas_anchor_rings_dialog.py
"""Real offscreen controls for the R1 extension of reviewed RSB lifecycle."""

import importlib
import os
import sys
from dataclasses import replace
from types import SimpleNamespace as NS
from unittest.mock import Mock

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
            if QtWidgets.QDialog.staticMetaObject.indexOfProperty(name) >= 0:
                raise AttributeError(f"Native property '{name}' cannot be overwritten")
            if callable(getattr(QtWidgets.QDialog, name, None)):
                raise AttributeError(f"Slot '{name}' cannot be overwritten")  # noqa: TRY004 - reproduce native PythonQt error
            super().__setattr__(name, value)

    class Label(QtWidgets.QLabel):
        font = property(QtWidgets.QLabel.font)

    class Combo(QtWidgets.QComboBox):
        currentIndex = property(QtWidgets.QComboBox.currentIndex)

    gui = NS(**{n: getattr(QtGui, n) for n in dir(QtGui) if n.startswith("Q")})
    gui.__dict__.update(
        {n: getattr(QtWidgets, n) for n in dir(QtWidgets) if n.startswith("Q")}
    )
    gui.QDialog, gui.QLabel, gui.QComboBox = Dialog, Label, Combo
    monkeypatch.setitem(sys.modules, "PythonQt", NS(QtCore=QtCore, QtGui=gui))
    for name in (
        "fontlabapp.glyphs.names.ui",
        "fontlabapp.metrics.canvas_rsb.ui",
        "fontlabapp.anchors.canvas_rings.ui",
    ):
        monkeypatch.delitem(sys.modules, name, raising=False)
    base = importlib.import_module("fontlabapp.metrics.canvas_rsb.ui")
    mod = importlib.import_module("fontlabapp.anchors.canvas_rings.ui")
    widget = QtWidgets.QWidget()
    widget.show()
    state = NS(
        package=NS(id=7, master="Regular", elidedName="Owned Rings"),
        canvas=NS(id=12),
        widget=widget,
    )
    handle = NS(closed=False, refresh=Mock(), raise_if_failed=Mock())
    handle.close = Mock(side_effect=lambda: setattr(handle, "closed", True))

    def draw(callback, **kwargs):
        assert kwargs == {"coordinates": "pixels"}
        state.callback = callback
        handle.closed = False
        return handle

    view = NS(widget=widget, draw=draw)

    class App:
        def glyph_window(self):
            view.canvas = state.canvas
            return view

        def close(self):
            handle.close()

    monkeypatch.setattr(base, "FontLab", App)
    monkeypatch.setattr(base, "current_package", lambda: state.package)
    snapshot = mod.api.Snapshot(7, 12, "Regular", ("Regular",), ())
    monkeypatch.setattr(mod.api, "capture", Mock(return_value=snapshot))
    monkeypatch.setattr(mod.api, "paint", Mock())
    dialog = mod.CanvasAnchorRingsDialog()
    yield dialog, state, handle, mod, base
    handle.close.side_effect = None
    if isValid(dialog):
        dialog.close()
    if isValid(widget):
        widget.close()
    APP.processEvents()


def test_controls_default_handle_sync_zero_snapshot_and_inherited_lifecycle(panel):
    dialog, _state, handle, mod, base = panel
    assert dialog.enabled_box.isChecked() and dialog.timer.isActive()
    assert [dialog.handle_size_combo.itemText(i) for i in range(3)] == ["5", "8", "12"]
    assert dialog.handle_size_combo.currentIndex == 1
    assert dialog.records.masters == ("Regular",) and not dialog.records.occurrences
    assert (
        "0 anchor pairs" in dialog.status.text()
        and "Owned Rings" in dialog.status.text()
    )
    assert (
        "Foreground" in dialog.subtitle.text() and "all tools" in dialog.subtitle.text()
    )
    for name in ("context", "toggle", "stop", "fail", "window_gone", "closeEvent"):
        assert getattr(type(dialog), name) is getattr(base.CanvasRSBDialog, name)
    dialog.handle_size_combo.setCurrentIndex(2)
    assert mod.api.capture.call_args.kwargs["handle_size"] == 12
    dialog.handle_size_combo.setCurrentIndex(0)
    assert mod.api.capture.call_args.kwargs["handle_size"] == 5
    dialog.enabled_box.click()
    assert handle.closed and not dialog.records and not dialog.timer.isActive()
    dialog.enabled_box.click()
    assert not handle.closed and dialog.timer.isActive()
    dialog.close_button.click()
    assert handle.closed and not dialog._connections and not dialog.timer.isActive()


@pytest.mark.parametrize(
    "fault",
    ["font", "master", "canvas", "closed", "hidden", "read", "partial", "drawing"],
)
def test_failed_or_stale_snapshot_stops_overlay_and_keeps_close(panel, fault):
    dialog, state, handle, mod, _base = panel
    if fault == "font":
        state.package.id = 99
    elif fault == "master":
        state.package.master = "Bold"
    elif fault == "canvas":
        state.canvas.id = 99
    elif fault == "closed":
        state.package = None
    elif fault == "hidden":
        state.widget.hide()
    elif fault == "read":
        mod.api.capture.side_effect = ValueError("read injected")
    elif fault == "partial":
        first = dialog.records
        mod.api.capture.side_effect = [
            first,
            replace(first, masters=("Regular", "Bold")),
        ]
    else:
        handle.raise_if_failed.side_effect = RuntimeError("drawing injected")
    dialog.refresh()
    assert not dialog.records and not dialog.enabled_box.isChecked()
    assert handle.closed and not dialog.timer.isActive()
    assert "Error:" in dialog.status.text() and dialog.close_button.isEnabled()


@pytest.mark.parametrize("error", [ValueError("paint injected"), ValueError()])
def test_paint_is_font_free_latched_and_recovers_only_after_safe_reactivation(
    panel, error
):
    dialog, state, handle, mod, _base = panel
    mod.api.paint.side_effect = error
    state.callback(Mock())
    assert dialog.paint_error and not dialog.records
    state.callback(Mock())
    assert mod.api.paint.call_count == 1, "Latched paint failure was retried in Qt"
    dialog.refresh()
    assert handle.closed and not dialog.timer.isActive()
    mod.api.paint.side_effect = None
    dialog.enabled_box.click()
    assert dialog.timer.isActive() and not dialog.paint_error
    mod.api.capture.side_effect = AssertionError("native read during paint")
    state.callback(Mock())
    assert mod.api.paint.call_count == 2


def test_parent_destruction_and_initial_no_font_leave_diagnosed_controls(panel):
    dialog, state, handle, mod, _base = panel
    state.widget.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert handle.closed and not dialog.records and not dialog.timer.isActive()
    state.package = None
    other = mod.CanvasAnchorRingsDialog()
    assert not other.enabled_box.isChecked() and other.close_button.isEnabled()
    assert "Open a font" in other.status.text()
    other.close()


def test_registry_retains_failed_cleanup_owner_then_relaunches_after_repair(
    panel, monkeypatch
):
    from fontlabapp.core import scripting

    dialog, _state, handle, mod, _base = panel
    native = scripting._native
    monkeypatch.setattr(
        scripting,
        "_native",
        lambda name: NS(MainWindow=lambda: None) if name == "fontlab" else native(name),
    )
    registry = {}
    monkeypatch.setattr(sys, "_fontlab_samples", registry, raising=False)
    assert scripting.show_script_dialog(lambda parent: dialog, mod.KEY) is dialog
    handle.close.side_effect = RuntimeError("cleanup injected")
    factory = Mock()
    assert scripting.show_script_dialog(factory, mod.KEY) is dialog
    assert registry[mod.KEY] is dialog and not dialog.timer.isActive()
    factory.assert_not_called()
    handle.close.side_effect = None
    replacement = scripting.show_script_dialog(mod.CanvasAnchorRingsDialog, mod.KEY)
    assert replacement is not dialog and registry[mod.KEY] is replacement
    assert replacement.timer.isActive()
    replacement.close_button.click()
    assert mod.KEY not in registry


def test_lazy_facades_return_the_core_and_panel(panel):
    from fontlabapp.core import scripting

    _dialog, _state, _handle, mod, _base = panel
    assert scripting.canvas_anchor_rings_api() is mod.api
    assert scripting.canvas_anchor_rings_dialog_type() is mod.CanvasAnchorRingsDialog


def test_handle_controls_recompute_and_repaint_only_changed_snapshots(panel):
    dialog, _state, handle, mod, _base = panel
    original = dialog.records

    def capture(canvas, package, *, handle_size):
        item = mod.api.Occurrence(
            (51, 41),
            31,
            "H",
            True,
            (1, 0, 0, 1, 0, 0),
            (("top", (0, 0)), ("bottom", (0, 0))),
            mod.api.rings(((0, 0), (0, 0)), 1, handle_size=handle_size),
        )
        return replace(original, occurrences=(item,))

    mod.api.capture.side_effect = capture
    dialog.refresh()
    assert "1 anchor pairs" in dialog.status.text()
    assert dialog.records.occurrences[0].rings[0].diameter == 16
    handle.refresh.reset_mock()
    dialog.refresh()
    handle.refresh.assert_not_called()
    dialog.handle_size_combo.setCurrentIndex(2)
    assert dialog.records.occurrences[0].rings[0].diameter == 24
    handle.refresh.assert_called_once()
    dialog.enabled_box.click()
    mod.api.capture.reset_mock()
    dialog.refresh()
    mod.api.capture.assert_not_called()


def test_invalid_handle_control_state_refuses_before_capture(panel):
    dialog, _state, handle, mod, _base = panel
    mod.api.capture.reset_mock()
    dialog.handle_size_combo.setCurrentIndex(-1)
    assert not dialog.enabled_box.isChecked() and handle.closed
    mod.api.capture.assert_not_called()
