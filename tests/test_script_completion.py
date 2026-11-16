# this_file: tests/test_script_completion.py
"""Verify shared standard dialog completion, including real subclass teardown."""

import sys
from types import SimpleNamespace as NS

import pytest

from fontlabapp.core.completion import install

pytestmark = pytest.mark.filterwarnings("error:libpyside:RuntimeWarning")


@pytest.fixture
def report_panel(monkeypatch):
    from test_tabular_width_dialog import panel

    yield from panel.__wrapped__(monkeypatch)


class Signal:
    def __init__(self):
        self.slots = []

    def connect(self, slot):
        self.slots.append(slot)

    def disconnect(self, slot):
        self.slots.remove(slot)

    def emit(self):
        for slot in tuple(self.slots):
            if slot in self.slots:
                slot()


class Owner:
    def __init__(self):
        self.finished, self.destroyed = Signal(), Signal()
        self._connections = []
        self.calls, self.refuse, self.fail = [], False, False

    def close(self):
        self.calls.append("close")
        if self.fail:
            raise RuntimeError("owned close failure")
        if self.refuse:
            return False
        self.finished.emit()
        self._completion_lifetime.stop()
        return True

    def show(self):
        self.calls.append("show")


def test_completion_routes_once_and_saved_callback_never_touches_closed_owner():
    owner = Owner()
    life = owner._completion_lifetime = install(owner, "owned")
    callback = owner.finished.slots[0]
    destroyed = owner.destroyed.slots[0]
    owner.finished.emit()
    assert owner.calls == ["close"] and life.closed and not life.hooks
    callback()
    destroyed()
    assert owner.calls == ["close"] and not owner.finished.slots


def test_refused_completion_retains_live_owner_and_can_retry():
    owner = Owner()
    life = owner._completion_lifetime = install(owner, "owned")
    owner.refuse = True
    owner.finished.emit()
    assert owner.calls == ["close", "show"] and not life.closed
    owner.refuse = False
    owner.finished.emit()
    assert life.closed and owner.calls == ["close", "show", "close"]


def test_close_failure_is_data_and_no_exception_escapes_signal():
    owner = Owner()
    life = owner._completion_lifetime = install(owner, "owned")
    owner.fail = True
    owner.finished.emit()
    assert "owned close failure" in life.error and not life.closed
    owner.fail = False
    owner.finished.emit()
    assert life.closed


def test_destroyed_marks_dead_before_callbacks_and_preserves_other_registry_owner(
    monkeypatch,
):
    owner = Owner()
    life = owner._completion_lifetime = install(owner, "owned")
    seen = []
    life.on_destroyed.append(lambda: seen.append(life.closed))
    other = object()
    monkeypatch.setattr(sys, "_fontlab_samples", {"owned": other}, raising=False)
    owner.destroyed.emit()
    assert life.closed and seen == [True] and life.dialog is None
    assert sys._fontlab_samples["owned"] is other
    owner.finished.emit()
    assert not owner.calls


def test_owned_destruction_removes_own_registry_and_records_callback_failure(
    monkeypatch,
):
    owner = Owner()
    life = owner._completion_lifetime = install(owner, "owned")
    life.on_destroyed.append(
        lambda: (_ for _ in ()).throw(RuntimeError("cleanup failed"))
    )
    monkeypatch.setattr(sys, "_fontlab_samples", {"owned": owner}, raising=False)
    owner.destroyed.emit()
    assert not sys._fontlab_samples and "cleanup failed" in life.errors[0]


def test_stop_attempts_remaining_hooks_when_one_disconnect_fails():
    owner = Owner()
    life = owner._completion_lifetime = install(owner, "owned")

    class Broken:
        def disconnect(self, slot):
            raise RuntimeError("owned disconnect failed")

    life.hooks.append((Broken(), lambda: None))
    life.stop()
    assert life.closed and not life.hooks and not owner.finished.slots
    assert "owned disconnect failed" in life.errors[0]


@pytest.mark.parametrize("refuse", [False, True])
def test_native_in_progress_close_dispatches_python_handler_once(report_panel, refuse):
    class InProgress(Owner):
        def close(self):
            self.calls.append("native-close")
            return True

        def closeEvent(self, event):
            self.calls.append("python-close")
            if self.refuse:
                event.ignore()
            else:
                self._completion_lifetime.stop()

    owner = InProgress()
    owner.refuse = refuse
    life = owner._completion_lifetime = install(owner, "owned")
    owner.finished.emit()
    assert owner.calls == ["native-close", "python-close"] + (
        ["show"] if refuse else []
    )
    assert life.closed is not refuse


@pytest.mark.parametrize("route", ["reject", "accept", "done", "escape"])
def test_actual_report_completion_releases_callbacks_registry_and_widget(
    report_panel, monkeypatch, route
):
    from PySide6 import QtCore
    from PySide6.QtTest import QTest
    from shiboken6 import isValid

    widget, _mod = report_panel
    monkeypatch.setattr(sys, "_fontlab_samples", {widget.KEY: widget}, raising=False)
    if route == "escape":
        widget.show()
        QTest.keyClick(widget, QtCore.Qt.Key_Escape)
    elif route == "done":
        widget.done(0)
    else:
        getattr(widget, route)()
    assert widget._closed and widget.report is None and not widget._connections
    assert widget._capture is widget._render is widget._status is None
    assert not sys._fontlab_samples
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert not isValid(widget)


def test_base_names_completion_uses_specialized_close_timer_and_source_cleanup(
    report_panel, monkeypatch
):
    from PySide6 import QtCore, QtWidgets

    from fontlabapp.glyphs.names.ui import NamesDialog

    class View(QtWidgets.QWidget):
        pass

    class Panel(NamesDialog):
        def __init__(self):
            super().__init__(None, "Owned", "owned")
            self.timer = QtCore.QTimer(self)
            self.timer.start(1000)
            self.view = View(self)
            self.view.before_draw = lambda: None
            self.source, self.teardowns = object(), 0

        def closeEvent(self, event):
            self.teardowns += 1
            self.source = self.view.before_draw = None
            super().closeEvent(event)

    panel = Panel()
    monkeypatch.setattr(sys, "_fontlab_samples", {"owned": panel}, raising=False)
    panel.reject()
    assert (
        panel.teardowns == 1 and panel.source is None and panel.view.before_draw is None
    )
    assert not panel.timer.isActive() and not sys._fontlab_samples
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


@pytest.mark.parametrize("phase", ["capture", "render", "status"])
@pytest.mark.parametrize("fail", [False, True])
def test_report_close_during_callback_never_reuses_closed_widgets(
    report_panel, phase, fail
):
    widget, _ = report_panel
    messages = []
    original = getattr(widget, "_" + phase)

    def close_during_callback(*args):
        result = original(*args)
        widget.close()
        messages.clear()
        if fail:
            raise RuntimeError("closed callback error")
        return result

    setattr(widget, "_" + phase, close_during_callback)
    widget.output = NS(
        clear=lambda: messages.append("clear"),
        setPlainText=lambda value: messages.append(value),
    )
    widget.status = NS(setText=messages.append)
    widget.refresh()
    assert widget._closed and widget.report is None and not messages
    if fail:
        assert "closed callback error" in widget.slot_error


def test_proof_completion_runs_real_painter_and_bound_source_teardown(report_panel):
    from PySide6 import QtCore, QtWidgets

    from fontlabapp.proof.inspect.ui import ProofDialog

    class View(QtWidgets.QWidget):
        pass

    panel = ProofDialog(None, "Owned proof", "proof")
    panel.view = View(panel)
    panel.view.rows = [1]
    panel.view.before_draw = panel.view.on_error = lambda: None
    panel.package, panel._bound_id, panel.glyphs = object(), 31, [object()]
    panel.reject()
    assert panel.view.before_draw is panel.view.on_error is None
    assert panel.package is None and panel._bound_id is None and not panel.glyphs
    assert not panel._connections
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_names_read_detects_source_switch_before_publishing_snapshot(
    report_panel, monkeypatch
):
    from PySide6 import QtCore

    import fontlabapp.glyphs.names.ui as names

    panel = names.NamesDialog(None, "Owned read", "read")
    monkeypatch.setattr(
        names,
        "current_package",
        lambda expected=None: NS(id=31) if expected is None else None,
    )

    @names.snapshot_refresh
    def read(dialog):
        return "detached result"

    with pytest.raises(ValueError, match="Font changed"):
        read(panel)
    assert not panel._snapshot_valid and panel._scanned_id is None
    panel.close()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_masters_completion_runs_extension_hook_and_releases_chart_source(report_panel):
    from PySide6 import QtCore, QtWidgets

    from fontlabapp.masters.inspect.ui import MastersDialog

    class View(QtWidgets.QWidget):
        pass

    class Panel(MastersDialog):
        def build(self):
            self.teardowns = 0
            self.chart = View(self)
            self.chart.masters = ["Regular"]
            self.chart.report = self.chart.before_draw = self.chart.on_error = lambda: (
                None
            )

        def refresh(self):
            pass

        def teardown(self):
            self.teardowns += 1

    panel = Panel(None, "Owned masters", "masters")
    panel.package, panel._bound_id = object(), 31
    panel.done(0)
    assert panel.teardowns == 1 and panel.package is None and panel._bound_id is None
    assert panel.chart.report is panel.chart.before_draw is panel.chart.on_error is None
    assert not panel._connections
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_font_info_completion_invalidates_preview_and_releases_source_plan(
    report_panel, monkeypatch
):
    import importlib

    from PySide6 import QtCore

    monkeypatch.delitem(sys.modules, "fontlabapp.fonts.info.ui", raising=False)
    mod = importlib.import_module("fontlabapp.fonts.info.ui")
    monkeypatch.setattr(mod, "current_package", lambda: None)

    class Panel(mod.FontInfoDialog):
        def setup(self):
            pass

        def refresh(self):
            pass

    panel = Panel(title="Owned info", subtitle="Source", key="info")
    panel.package, panel.package_id, panel.preview_master = object(), 31, "Regular"
    panel._preview_valid, panel._plan = True, [object()]
    panel.accept()
    assert not panel._preview_valid and not panel._plan
    assert panel.package is panel.package_id is panel.preview_master is None
    assert not panel._connections
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
