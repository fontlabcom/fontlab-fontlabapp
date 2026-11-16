# this_file: tests/test_canvas_rsb_dialog.py
"""Real offline Qt controls with owned overlay doubles; no FontLab access."""

import importlib
import os
import sys
from types import SimpleNamespace as NS
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6 import QtCore, QtGui, QtWidgets
from shiboken6 import isValid

APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def panel(monkeypatch):
    qapp = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    class Dialog(QtWidgets.QDialog):
        palette = property(QtWidgets.QDialog.palette)

        def __setattr__(self, name, value):
            if QtWidgets.QDialog.staticMetaObject.indexOfProperty(name) >= 0:
                raise AttributeError(f"Native property '{name}' cannot be overwritten")
            if callable(getattr(QtWidgets.QDialog, name, None)):
                raise AttributeError(  # noqa: TRY004 - reproduce PythonQt's native error
                    f"Slot '{name}' cannot be overwritten"
                )
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
    for name in ["fontlabapp.glyphs.names.ui", "fontlabapp.metrics.canvas_rsb.ui"]:
        monkeypatch.delitem(sys.modules, name, raising=False)
    mod = importlib.import_module("fontlabapp.metrics.canvas_rsb.ui")
    widget = QtWidgets.QWidget()
    widget.show()
    package = NS(id=7, master="Regular", elidedName="Owned Test")
    state = NS(package=package, canvas=NS(id=12), widget=widget)
    handle = NS(closed=False, refresh=Mock(), raise_if_failed=Mock())
    handle.close = Mock(side_effect=lambda: setattr(handle, "closed", True))

    def draw(callback, **kwargs):
        assert kwargs == {"coordinates": "pixels"}
        state.callback = callback
        handle.closed = False
        return handle

    window = NS(widget=widget, draw=draw)

    class App:
        def glyph_window(self):
            window.canvas = state.canvas
            return window

        def close(self):
            handle.close()

    monkeypatch.setattr(mod, "FontLab", App)
    monkeypatch.setattr(mod, "current_package", lambda: state.package)
    monkeypatch.setattr(mod.api, "capture", lambda *args: ("first", "second"))
    monkeypatch.setattr(mod.api, "paint", Mock())
    dialog = mod.CanvasRSBDialog()
    yield dialog, state, handle, mod
    if isValid(dialog):
        dialog.close()
    if isValid(widget):
        widget.close()
    qapp.processEvents()


def test_actual_qt_controls_enable_direction_refresh_and_close(panel):
    dialog, state, handle, mod = panel
    assert dialog.enabled_box.isChecked() and dialog.timer.isActive()
    assert dialog.direction.count() == 2 and dialog.direction.currentIndex == 0
    assert dialog.records == ("first", "second")
    assert "Owned Test" in dialog.status.text() and "Regular" in dialog.status.text()
    assert "Foreground" in dialog.subtitle.text()
    state.callback(Mock())
    mod.api.paint.assert_called_once()
    dialog.direction.setCurrentIndex(1)
    dialog.enabled_box.click()
    assert not dialog.timer.isActive() and not dialog.records and handle.closed
    dialog.enabled_box.click()
    assert dialog.timer.isActive() and not handle.closed
    dialog.close_button.click()
    assert handle.closed and not dialog.timer.isActive() and not dialog._connections


def test_native_slots_remain_callable_and_cannot_be_shadowed(panel):
    dialog, state, _handle, _mod = panel
    assert dialog.glyph_view.widget is state.widget
    assert callable(dialog.window), "Glyph view replaced QWidget.window()"
    with pytest.raises(AttributeError, match="Slot 'window' cannot be overwritten"):
        dialog.window = state.widget
    with pytest.raises(AttributeError, match="Native property 'enabled'"):
        dialog.enabled = state.widget


@pytest.mark.parametrize(
    "kind", ["font", "master", "window", "closed", "read", "paint"]
)
def test_fault_or_stale_context_stops_overlay_and_keeps_close(panel, kind):
    dialog, state, handle, mod = panel
    if kind == "font":
        state.package = NS(id=99, master="Regular")
    elif kind == "master":
        state.package.master = "Bold"
    elif kind == "window":
        state.canvas = NS(id=99)
    elif kind == "closed":
        state.package = None
    elif kind == "read":
        monkey = Mock(side_effect=ValueError("read failed"))
        mod.api.capture = monkey
    else:
        mod.api.paint.side_effect = ValueError("paint failed")
        state.callback(Mock())
    dialog.refresh()
    assert not dialog.records and handle.closed and not dialog.timer.isActive()
    assert not dialog.enabled_box.isChecked() and "Error:" in dialog.status.text()
    assert dialog.close_button.isEnabled(), "Fault hid the recovery control"


def test_parent_destruction_releases_handles_without_rebinding(panel):
    dialog, state, handle, _mod = panel
    state.widget.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert handle.closed and not dialog.records and not dialog.timer.isActive()
    assert "closed" in dialog.status.text().lower()


def test_initial_no_font_and_missing_window_leave_complete_controls(panel):
    _dialog, state, _handle, mod = panel
    state.package = None
    other = mod.CanvasRSBDialog()
    assert not other.enabled_box.isChecked() and other.close_button.isEnabled()
    assert "Open a font" in other.status.text()
    other.close()


def test_cleanup_fault_is_visible_and_stops_timer(panel):
    dialog, _state, handle, _mod = panel
    handle.close.side_effect = RuntimeError("cleanup injected")
    dialog.fail(ValueError("read injected"))
    assert not dialog.timer.isActive() and not dialog.records
    assert "cleanup injected" in dialog.status.text()


def test_partial_snapshot_or_activation_fault_leaves_diagnosed_panel(panel):
    dialog, _state, handle, mod = panel
    outputs = iter([("a",), ("b",)])
    mod.api.capture = lambda *a: next(outputs)
    dialog.refresh()
    assert handle.closed and not dialog.records
    dialog.enabled_box.click()
    assert "Error:" in dialog.status.text()


def test_paint_failure_can_be_reenabled_after_repair(panel):
    dialog, state, handle, mod = panel
    mod.api.paint.side_effect = ValueError("paint injected")
    state.callback(Mock())
    dialog.refresh()
    mod.api.paint.side_effect = None
    dialog.enabled_box.click()
    assert dialog.timer.isActive() and not handle.closed
    assert dialog.records and not dialog.paint_error


def test_toggle_cleanup_failure_is_diagnosed_without_escaping(panel):
    dialog, _state, handle, _mod = panel
    handle.close.side_effect = RuntimeError("cleanup injected")
    dialog.enabled_box.setChecked(False)
    assert "cleanup injected" in dialog.status.text()
    assert not dialog.timer.isActive() and not dialog.records
    handle.close.side_effect = None


def test_stopped_overlay_callback_cannot_paint_old_snapshot(panel):
    dialog, state, _handle, mod = panel
    callback = state.callback
    dialog.enabled_box.click()
    callback(Mock())
    mod.api.paint.assert_not_called()


def test_failed_cleanup_is_retried_before_reactivation(panel):
    dialog, _state, handle, _mod = panel
    owner = dialog.app
    handle.close.side_effect = RuntimeError("retry cleanup")
    dialog.enabled_box.click()
    assert dialog.app is owner, "Lost the owner of resources awaiting cleanup"
    handle.close.side_effect = None
    dialog.enabled_box.click()
    assert dialog.app is not owner and dialog.timer.isActive()


def test_transient_disconnect_failure_is_retried_and_close_removes_callback(panel):
    dialog, state, handle, _mod = panel
    window, slot = dialog.glyph_view, dialog._window_slot
    signal = state.widget.destroyed
    attempts = []

    def disconnect(callback):
        attempts.append(callback)
        if len(attempts) == 1:
            raise RuntimeError("transient disconnect failure")
        signal.disconnect(callback)

    window.widget = NS(destroyed=NS(disconnect=disconnect))
    with pytest.raises(RuntimeError, match="transient disconnect failure"):
        dialog.stop()
    assert handle.closed, "Signal failure skipped independent drawing cleanup"
    assert dialog.glyph_view is window and dialog._window_slot is slot
    assert not dialog.timer.isActive() and not dialog.records
    dialog.stop()
    assert attempts == [slot, slot], "Lost the failed disconnect's retry ownership"
    assert dialog.glyph_view is None and dialog._window_slot is None
    dialog.window_gone = Mock()
    dialog.close()
    state.widget.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    dialog.window_gone.assert_not_called()


def test_parent_destruction_after_disconnect_failure_clears_dead_retry_handles(panel):
    dialog, state, _handle, _mod = panel
    signal = NS(disconnect=Mock(side_effect=RuntimeError("disconnect failed")))
    dialog.glyph_view.widget = NS(destroyed=signal)
    with pytest.raises(RuntimeError, match="disconnect failed"):
        dialog.stop()
    state.widget.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert dialog.glyph_view is None and dialog._window_slot is None
    signal.disconnect.assert_called_once()
    assert "closed" in dialog.status.text().lower()
    dialog.stop()
    signal.disconnect.assert_called_once()


def test_close_waits_for_failed_native_disconnect_before_destroying_panel(panel):
    dialog, state, _handle, _mod = panel
    signal = state.widget.destroyed
    disconnect = Mock(side_effect=RuntimeError("persistent disconnect failure"))
    dialog.glyph_view.widget = NS(destroyed=NS(disconnect=disconnect))
    try:
        assert not dialog.close(), (
            "Destroyed controls while callback remained connected"
        )
        assert dialog._window_slot is not None and isValid(dialog)
        assert "persistent disconnect failure" in dialog.status.text()
    finally:
        disconnect.side_effect = signal.disconnect
    dialog.window_gone = Mock()
    assert dialog.close(), "Close did not recover after native disconnect succeeded"
    state.widget.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    dialog.window_gone.assert_not_called()


def test_close_when_drawing_cleanup_keeps_failing_then_retains_panel_for_retry(panel):
    dialog, _state, handle, _mod = panel
    owner = dialog.app
    handle.close.side_effect = RuntimeError("persistent drawing cleanup failure")
    try:
        assert not dialog.close(), (
            "Destroyed panel while its drawing owner remained live"
        )
        assert dialog.app is owner and isValid(dialog)
        assert "persistent drawing cleanup failure" in dialog.status.text()
    finally:
        handle.close.side_effect = None
    assert dialog.close(), "Close did not retry the retained drawing owner"


@pytest.mark.parametrize("failure", ["disconnect", "drawing"])
def test_relaunch_when_persistent_cleanup_fails_then_keeps_registered_panel_until_repair(
    panel, monkeypatch, failure
):
    from fontlabapp.core import scripting

    dialog, state, handle, mod = panel
    native = scripting._native
    monkeypatch.setattr(
        scripting,
        "_native",
        lambda name: NS(MainWindow=lambda: None) if name == "fontlab" else native(name),
    )
    registry = {}
    monkeypatch.setattr(sys, "_fontlab_samples", registry, raising=False)
    factory = Mock(return_value=dialog)
    assert scripting.show_script_dialog(factory, mod.KEY) is dialog
    factory.reset_mock()
    window = dialog.glyph_view
    disconnect = Mock(side_effect=RuntimeError("persistent disconnect failure"))
    if failure == "disconnect":
        window.widget = NS(destroyed=NS(disconnect=disconnect))
    else:
        handle.close.side_effect = RuntimeError("persistent drawing cleanup failure")
    try:
        assert scripting.show_script_dialog(factory, mod.KEY) is dialog
        factory.assert_not_called()
        assert registry[mod.KEY] is dialog and dialog.isVisible() and isValid(dialog)
        assert "persistent" in dialog.status.text()
    finally:
        window.widget = state.widget
        handle.close.side_effect = None
    replacement_factory = Mock(side_effect=mod.CanvasRSBDialog)
    replacement = scripting.show_script_dialog(replacement_factory, mod.KEY)
    try:
        assert replacement is not dialog and registry[mod.KEY] is replacement
        replacement_factory.assert_called_once_with(None)
        assert replacement.timer.isActive()
    finally:
        replacement.close()
    assert mod.KEY not in registry
