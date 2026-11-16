# this_file: tests/test_widgets_recovery.py
"""Independent retry/refusal/factory regressions, with real standalone Qt."""

from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from test_spacing_worksheet import GUI, QtCore, drain, valid
import fontlabapp.qt.widgets as widgets


class Signal:
    def __init__(self):
        self.slots = []
        self.failure = None

    def connect(self, slot):
        self.slots.append(slot)

    def disconnect(self, slot):
        if self.failure:
            raise self.failure
        self.slots.remove(slot)
        return True

    def emit(self):
        for slot in tuple(self.slots):
            slot()


def fake_owner():
    widget = NS(
        destroyed=Signal(),
        hide=Mock(),
        close=Mock(return_value=True),
        deleteLater=Mock(),
    )
    main = NS(removeDockWidget=Mock())
    return widgets.OwnedWidget(widget, widget, main=main), widget, main


@pytest.mark.parametrize("stage", ["close", "remove", "delete", "disconnect"])
@pytest.mark.parametrize("destroy", [False, True])
def test_cleanup_failure_retains_owner_observation_and_retries_only_unfinished(
    stage, destroy
):
    owner, widget, main = fake_owner()
    error = RuntimeError(stage)
    target = {
        "close": widget.close,
        "remove": main.removeDockWidget,
        "delete": widget.deleteLater,
    }.get(stage)
    if target is not None:
        target.side_effect = error
    else:
        widget.destroyed.failure = error
    with pytest.raises(RuntimeError) as caught:
        owner.close()
    assert caught.value is error
    assert owner.widget is widget and not owner.closed
    assert owner._destroyed in widget.destroyed.slots, (
        "Keep destruction observation while recovery remains"
    )
    if destroy:
        widget.destroyed.emit()
        before = (
            widget.close.call_count,
            main.removeDockWidget.call_count,
            widget.deleteLater.call_count,
        )
        owner.close()
        assert before == (
            widget.close.call_count,
            main.removeDockWidget.call_count,
            widget.deleteLater.call_count,
        )
    else:
        if target is not None:
            target.side_effect = None
        widget.destroyed.failure = None
        owner.close()
        owner.close()
        assert widget.close.call_count == (2 if stage == "close" else 1)
        assert main.removeDockWidget.call_count == (2 if stage == "remove" else 1)
        assert widget.deleteLater.call_count == (2 if stage == "delete" else 1)
        assert not widget.destroyed.slots
    assert (
        owner.closed
        and owner.widget is None
        and owner.content is None
        and owner._main is None
    )


def test_close_refusal_preserves_visible_registered_owner_then_accepts():
    owner, widget, main = fake_owner()
    widget.close.return_value = False
    assert owner.close() is False
    assert not owner.closed and owner.widget is widget and widget.destroyed.slots
    widget.hide.assert_not_called()
    main.removeDockWidget.assert_not_called()
    widget.deleteLater.assert_not_called()
    widget.close.return_value = True
    owner.close()
    assert owner.closed


def test_recursive_close_from_native_event_does_not_double_teardown():
    owner, widget, main = fake_owner()
    widget.close.side_effect = lambda: owner.close() or True
    owner.close()
    assert owner.closed and widget.close.call_count == 1
    widget.deleteLater.assert_called_once()
    main.removeDockWidget.assert_called_once()


@pytest.fixture
def binding(monkeypatch):
    qt = NS(QtGui=GUI, QtCore=QtCore)
    monkeypatch.setattr(widgets, "_native", lambda name: qt)
    yield qt
    drain()


def test_real_refused_close_parent_destruction_and_retry(binding):
    class Refusing(GUI.QWidget):
        allow = False

        def closeEvent(self, event):
            if self.allow:
                event.accept()
            else:
                event.ignore()

    parent = GUI.QWidget()
    child = Refusing(parent, QtCore.Qt.Tool)
    owner = widgets.OwnedWidget(child, child)
    child.show()
    assert owner.close() is False and child.isVisible() and valid(child)
    assert not owner.closed and owner.widget is child
    parent.deleteLater()
    drain()
    assert not valid(child) and owner.closed and owner.widget is None
    owner.close()
    child = Refusing(None)
    owner = widgets.OwnedWidget(child, child)
    assert owner.close() is False
    child.allow = True
    owner.close()
    drain()
    assert not valid(child) and owner.closed


@pytest.mark.parametrize("visible", [False, True])
def test_panel_keeps_dock_area_content_parent_and_floating_priority(binding, visible):
    main = GUI.QMainWindow()
    if visible:
        main.show()
    owner = widgets.create_panel(
        main, "Owned dock", lambda content: content.setObjectName("content"), "right"
    )
    dock = owner.widget
    try:
        assert dock.parent() is main and dock.widget() is owner.content
        assert main.dockWidgetArea(dock) == QtCore.Qt.RightDockWidgetArea
        assert (
            dock.objectName().startswith("fontlabappPanel_")
            and owner.content.objectName() == "content"
        )
        assert dock.isFloating() is (not visible) and dock.isVisible()
        if not visible:
            assert dock.windowFlags() & QtCore.Qt.WindowStaysOnTopHint
            dock.setFloating(False)
            dock.setFloating(True)
            assert dock.isVisible(), (
                "Applying flags during later floating must restore visibility"
            )
            assert dock.windowFlags() & QtCore.Qt.WindowStaysOnTopHint
        else:
            assert not dock.windowFlags() & QtCore.Qt.WindowStaysOnTopHint
    finally:
        owner.close()
        main.deleteLater()
        drain()
    assert not valid(dock)


def test_panel_docked_while_main_hidden_floats_again_and_stays_visible(binding):
    main = GUI.QMainWindow()
    owner = widgets.create_panel(main, "Owned dock", None, "right")
    dock = owner.widget
    try:
        assert dock.isFloating() and dock.isVisible()
        dock.setFloating(False)  # what a title-bar double-click does
        drain()
        assert dock.isFloating(), "a dock in a hidden MainWindow must float again"
        assert dock.isVisible(), "re-floated dock must stay visible"
        assert main.dockWidgetArea(dock) == QtCore.Qt.RightDockWidgetArea
    finally:
        owner.close()
        main.deleteLater()
        drain()


def test_panel_docked_while_main_visible_stays_docked(binding):
    main = GUI.QMainWindow()
    main.show()
    owner = widgets.create_panel(main, "Owned dock", None, "right")
    dock = owner.widget
    try:
        dock.setFloating(True)
        dock.setFloating(False)
        drain()
        assert not dock.isFloating(), "a visible MainWindow keeps normal docking"
    finally:
        owner.close()
        main.deleteLater()
        drain()


@pytest.mark.parametrize("factory", ["dialog", "widget", "panel"])
@pytest.mark.parametrize("failure", ["build", "show"])
def test_factory_failure_deletes_created_widget_and_preserves_primary(
    binding, monkeypatch, factory, failure
):
    made = []
    base = {"dialog": GUI.QDialog, "widget": GUI.QWidget, "panel": GUI.QDockWidget}[
        factory
    ]
    error = ValueError(f"{factory} {failure}")

    class Fails(base):
        def __init__(self, *args):
            base.__init__(self, *args)
            made.append(self)

        def show(self):
            if failure == "show":
                raise error
            return base.show(self)

    monkeypatch.setattr(
        binding.QtGui,
        {"dialog": "QDialog", "widget": "QWidget", "panel": "QDockWidget"}[factory],
        Fails,
    )

    def build(content):
        if failure == "build":
            raise error

    main = GUI.QMainWindow()
    try:
        with pytest.raises(ValueError) as caught:
            if factory == "dialog":
                widgets.create_dialog(main, "Title", build)
            elif factory == "widget":
                widgets.create_widget(main, build)
            else:
                widgets.create_panel(main, "Title", build, "left")
        assert caught.value is error
        drain()
        assert not valid(made[0]), "Failed factories must retire their allocated owner"
    finally:
        main.deleteLater()
        drain()


def test_factory_cleanup_failure_exposes_primary_cleanup_and_retryable_owner(
    binding, monkeypatch
):
    primary, cleanup = ValueError("build failed"), RuntimeError("delete failed")
    base = GUI.QWidget

    class Fails(base):
        fail = True

        def deleteLater(self):
            if self.fail:
                raise cleanup
            return base.deleteLater(self)

    monkeypatch.setattr(binding.QtGui, "QWidget", Fails)
    with pytest.raises(ExceptionGroup) as caught:
        widgets.create_widget(None, Mock(side_effect=primary))
    assert caught.value.exceptions == (primary, cleanup)
    owner = caught.value.owner
    assert owner.widget is not None and not owner.closed
    owner.widget.fail = False
    owner.close()
    drain()
    assert owner.closed


@pytest.mark.parametrize("refusal", [False, True])
def test_owned_callback_disconnect_failure_keeps_exact_slot_fenced_and_retryable(
    refusal,
):
    owner, widget, main = fake_owner()
    signal, slot = Signal(), lambda: None
    signal.connect(slot)
    owner._connections = [(signal, slot)]
    if refusal:
        disconnect = signal.disconnect
        signal.disconnect = Mock(return_value=False)
    else:
        error = RuntimeError("owned disconnect")
        signal.failure = error
    with pytest.raises(RuntimeError) as caught:
        owner.close()
    if not refusal:
        assert caught.value is error
    assert owner._connections == [(signal, slot)] and signal.slots == [slot]
    assert owner.widget is widget and not owner.closed and widget.destroyed.slots
    widget.deleteLater.assert_not_called()
    if refusal:
        signal.disconnect = disconnect
    else:
        signal.failure = None
    owner.close()
    assert not signal.slots and owner.closed
    widget.close.assert_called_once()
    main.removeDockWidget.assert_called_once()


def test_destroyed_disconnect_refusal_never_claims_cleanup_and_observes_actual_destruction():
    owner, widget, main = fake_owner()
    widget.destroyed.disconnect = Mock(return_value=False)
    with pytest.raises(RuntimeError, match="destruction disconnect refused"):
        owner.close()
    assert owner.widget is widget and not owner.closed and widget.destroyed.slots
    widget.destroyed.emit()
    assert owner.closed and owner.widget is None
    owner.close()
    widget.close.assert_called_once()
    widget.deleteLater.assert_called_once()


@pytest.mark.parametrize("stage", ["close", "remove", "delete", "owned_disconnect"])
def test_destruction_during_cleanup_stage_stops_accessing_dead_wrappers(stage):
    owner, widget, main = fake_owner()
    signal = Signal()
    signal.connect(lambda: None)
    if stage == "owned_disconnect":
        owner._connections = [(signal, signal.slots[0])]
        signal.disconnect = Mock(side_effect=lambda slot: widget.destroyed.emit())
    else:
        target = {
            "close": widget.close,
            "remove": main.removeDockWidget,
            "delete": widget.deleteLater,
        }[stage]
        target.side_effect = lambda *args: widget.destroyed.emit()
    owner.close()
    assert owner.closed and owner.widget is None
    if stage == "close":
        main.removeDockWidget.assert_not_called()
    if stage in {"close", "remove", "owned_disconnect"}:
        widget.deleteLater.assert_not_called()


@pytest.mark.parametrize("factory", ["dialog", "panel"])
def test_early_factory_setup_failure_cleans_allocated_owner(
    binding, monkeypatch, factory
):
    made = []
    error = RuntimeError("early setup")
    base = GUI.QDialog if factory == "dialog" else GUI.QDockWidget

    class Fails(base):
        def __init__(self, *args):
            super().__init__(*args)
            made.append(self)

        def setModal(self, value):
            raise error

        def setObjectName(self, value):
            raise error

    monkeypatch.setattr(
        binding.QtGui, "QDialog" if factory == "dialog" else "QDockWidget", Fails
    )
    main = GUI.QMainWindow()
    with pytest.raises(RuntimeError) as caught:
        if factory == "dialog":
            widgets.create_dialog(main, "Title", None)
        else:
            widgets.create_panel(main, "Title", None, "left")
    assert caught.value is error
    drain()
    assert not valid(made[0])
    main.deleteLater()
    drain()


def test_floating_flags_preserve_window_type_before_first_show(binding, monkeypatch):
    seen = []
    base = GUI.QDockWidget

    class Observed(base):
        def setWindowFlags(self, flags):
            seen.append(("flags", self.windowType(), flags & QtCore.Qt.WindowType_Mask))
            super().setWindowFlags(flags)

        def show(self):
            seen.append(
                ("show", bool(self.windowFlags() & QtCore.Qt.WindowStaysOnTopHint))
            )
            super().show()

    monkeypatch.setattr(binding.QtGui, "QDockWidget", Observed)
    main = GUI.QMainWindow()
    owner = widgets.create_panel(main, "Title", None, "left")
    assert seen[-1] == ("show", True)
    assert any(item[0] == "flags" for item in seen)
    assert all(item[1] == item[2] for item in seen if item[0] == "flags")
    owner.close()
    main.deleteLater()
    drain()


def test_float_transition_restores_visible_dock_when_main_becomes_hidden(binding):
    main = GUI.QMainWindow()
    main.show()
    owner = widgets.create_panel(main, "Title", None, "bottom")
    dock = owner.widget
    assert not dock.isFloating()
    main.hide()
    dock.setFloating(True)
    dock.show()
    assert dock.isVisible() and dock.windowFlags() & QtCore.Qt.WindowStaysOnTopHint
    dock.setFloating(False)
    dock.setFloating(True)
    assert dock.isVisible() and dock.windowFlags() & QtCore.Qt.WindowStaysOnTopHint
    owner.close()
    main.deleteLater()
    drain()


def test_embedded_and_hidden_widgets_retain_requested_behavior(binding):
    parent = GUI.QWidget()
    parent.show()
    hidden = widgets.create_widget(parent, None, show=False)
    embedded = widgets.create_widget(parent, None)
    floating = widgets.create_widget(parent, None, floating=True)
    assert hidden.widget.parent() is parent and not hidden.widget.isVisible()
    assert embedded.widget.parent() is parent and not embedded.widget.isWindow()
    assert embedded.widget.isVisible()
    assert floating.widget.windowType() == QtCore.Qt.Tool
    for owner in (hidden, embedded, floating):
        owner.close()
    parent.deleteLater()
    drain()


def test_factory_refused_cleanup_retains_owner_and_primary_until_explicit_retry(
    binding, monkeypatch
):
    primary = ValueError("build failed")
    base = GUI.QWidget

    class Refuses(base):
        allow = False

        def closeEvent(self, event):
            event.accept() if self.allow else event.ignore()

    monkeypatch.setattr(binding.QtGui, "QWidget", Refuses)
    with pytest.raises(ExceptionGroup) as caught:
        widgets.create_widget(None, Mock(side_effect=primary))
    assert caught.value.exceptions[0] is primary
    assert "refused" in str(caught.value.exceptions[1])
    owner = caught.value.owner
    widget = owner.widget
    assert valid(widget) and not owner.closed
    widget.allow = True
    owner.close()
    drain()
    assert not valid(widget) and owner.closed


def test_panel_callback_disconnect_failure_keeps_callback_but_fences_window_changes(
    binding, monkeypatch
):
    main = GUI.QMainWindow()
    owner = widgets.create_panel(main, "Title", None, "left")
    dock = owner.widget
    signal, callback = owner._connections[0]
    error = RuntimeError("disconnect failed")
    owner._connections[0] = (NS(disconnect=Mock(side_effect=error)), callback)
    with pytest.raises(RuntimeError) as caught:
        owner.close()
    assert caught.value is error and valid(dock) and owner.widget is dock
    monkeypatch.setattr(
        dock,
        "windowFlags",
        Mock(side_effect=AssertionError("retired callback touched Qt")),
    )
    callback(True)
    assert owner.last_error is None, (
        "Accepted Close fences priority callback while cleanup retries"
    )
    owner._connections[0] = (signal, callback)
    owner.close()
    main.deleteLater()
    drain()
    assert owner.closed and not valid(dock)


@pytest.mark.parametrize("stage", ["flags", "show"])
def test_later_floating_priority_failure_is_diagnosed_and_keeps_owner(
    binding, monkeypatch, stage
):
    main = GUI.QMainWindow()
    main.show()
    owner = widgets.create_panel(main, "Title", None, "left")
    dock = owner.widget
    main.hide()
    dock.setFloating(True)
    dock.show()
    # Remove the hint to force this exact transition setter/show path.
    GUI.QDockWidget.setWindowFlags(
        dock, dock.windowFlags() & ~QtCore.Qt.WindowStaysOnTopHint
    )
    GUI.QDockWidget.show(dock)
    error = RuntimeError("later " + stage)
    method = "setWindowFlags" if stage == "flags" else "show"
    monkeypatch.setattr(dock, method, Mock(side_effect=error))
    callback = owner._connections[0][1]
    callback(True)
    assert owner.last_error is error and owner.widget is dock and not owner.closed
    monkeypatch.delattr(dock, method)
    GUI.QDockWidget.show(dock)
    callback(True)
    assert dock.isVisible() and dock.windowFlags() & QtCore.Qt.WindowStaysOnTopHint
    owner.close()
    main.deleteLater()
    drain()


def test_panel_initial_flag_failure_cleans_owned_dock_without_masking_error(
    binding, monkeypatch
):
    made = []
    error = RuntimeError("initial flags")
    base = GUI.QDockWidget

    class Fails(base):
        def __init__(self, *args):
            super().__init__(*args)
            made.append(self)

        def setWindowFlags(self, flags):
            raise error

    monkeypatch.setattr(binding.QtGui, "QDockWidget", Fails)
    main = GUI.QMainWindow()
    with pytest.raises(RuntimeError) as caught:
        widgets.create_panel(main, "Title", None, "left")
    assert caught.value is error
    drain()
    assert not valid(made[0])
    main.deleteLater()
    drain()


def test_visible_parent_user_undocking_gets_priority_and_keeps_visible_dock(binding):
    main = GUI.QMainWindow()
    main.show()
    owner = widgets.create_panel(main, "Title", None, "left")
    dock = owner.widget
    assert (
        not dock.isFloating()
        and not dock.windowFlags() & QtCore.Qt.WindowStaysOnTopHint
    )
    dock.setFloating(True)
    assert dock.isVisible() and dock.windowFlags() & QtCore.Qt.WindowStaysOnTopHint
    assert (
        main.dockWidgetArea(dock) == QtCore.Qt.LeftDockWidgetArea
        and dock.parent() is main
    )
    owner.close()
    main.deleteLater()
    drain()


@pytest.mark.parametrize("factory", ["dialog", "widget", "panel"])
@pytest.mark.parametrize("connect_refuses", [False, True])
@pytest.mark.parametrize("cleanup_fails", [False, True])
@pytest.mark.parametrize("destroy_parent", [False, True])
def test_initial_observer_failure_retires_allocation_or_retains_exact_errors_and_recovery(
    binding, monkeypatch, factory, connect_refuses, cleanup_fails, destroy_parent
):
    made = []
    primary = RuntimeError("observer connect failed")
    cleanup = RuntimeError("initial delete failed")
    name = {"dialog": "QDialog", "widget": "QWidget", "panel": "QDockWidget"}[factory]
    base = getattr(GUI, name)

    class Fails(base):
        def __init__(self, *args):
            super().__init__(*args)
            self.probe = Signal()
            self.allow_observer = False
            self.allow_delete = not cleanup_fails
            self.probe.connect = self.connect_probe
            made.append(self)

        def __getattribute__(self, name):
            if name == "destroyed":
                return object.__getattribute__(self, "probe")
            return super().__getattribute__(name)

        def connect_probe(self, slot):
            if not self.allow_observer:
                if connect_refuses:
                    return False
                raise primary
            self.probe.slots.append(slot)
            return True

        def deleteLater(self):
            if not self.allow_delete:
                raise cleanup
            super().deleteLater()

    monkeypatch.setattr(binding.QtGui, name, Fails)
    parent = GUI.QMainWindow()
    with pytest.raises(ExceptionGroup if cleanup_fails else RuntimeError) as caught:
        if factory == "dialog":
            widgets.create_dialog(parent, "Title", None)
        elif factory == "widget":
            widgets.create_widget(parent, None)
        else:
            widgets.create_panel(parent, "Title", None, "left")
    widget = made[0]
    error = caught.value.exceptions[0] if cleanup_fails else caught.value
    assert "refused" in str(error) if connect_refuses else error is primary
    if cleanup_fails:
        assert caught.value.exceptions[1] is cleanup
        owner = caught.value.owner
        assert owner.widget is widget and not owner.closed and valid(widget)
        if destroy_parent:
            parent.deleteLater()
            drain()
            assert owner.closed and owner.widget is None and not valid(widget)
            owner.close()
            return
        widget.allow_observer = widget.allow_delete = True
        owner.close()
        assert owner.closed
    drain()
    assert not valid(widget), "Failed initial observer must not abandon the allocation"
    parent.deleteLater()
    drain()


@pytest.mark.parametrize("cleanup_fails", [False, True])
def test_panel_priority_connect_refusal_never_records_nonexistent_callback(
    binding, monkeypatch, cleanup_fails
):
    made = []
    cleanup = RuntimeError("connect-refusal cleanup failed")
    base = GUI.QDockWidget

    class Refuses(base):
        def __init__(self, *args):
            super().__init__(*args)
            self.probe = NS(
                connect=Mock(return_value=False), disconnect=Mock(return_value=False)
            )
            self.allow_delete = not cleanup_fails
            made.append(self)

        def __getattribute__(self, name):
            if name == "topLevelChanged":
                return object.__getattribute__(self, "probe")
            return super().__getattribute__(name)

        def deleteLater(self):
            if not self.allow_delete:
                raise cleanup
            super().deleteLater()

    monkeypatch.setattr(binding.QtGui, "QDockWidget", Refuses)
    parent = GUI.QMainWindow()
    with pytest.raises(ExceptionGroup if cleanup_fails else RuntimeError) as caught:
        widgets.create_panel(parent, "Title", None, "left")
    child = made[0]
    primary = caught.value.exceptions[0] if cleanup_fails else caught.value
    assert "priority" in str(primary) and "refused" in str(primary)
    child.probe.disconnect.assert_not_called()
    if cleanup_fails:
        assert caught.value.exceptions[1] is cleanup
        owner = caught.value.owner
        assert owner.widget is child and not owner._connections
        child.allow_delete = True
        owner.close()
    drain()
    assert not valid(child)
    parent.deleteLater()
    drain()


@pytest.mark.parametrize("close_result", ["refuse", "error"])
@pytest.mark.parametrize("parent_disconnect", ["success", "error", "refuse"])
@pytest.mark.parametrize("finish", ["retry", "parent_death"])
def test_reobserved_child_destroyed_after_close_refusal_keeps_live_parent_teardown_reachable(
    binding, close_result, parent_disconnect, finish
):
    primary = RuntimeError("child observation failed")
    cleanup = RuntimeError("initial child deletion failed")
    disconnect_error = RuntimeError("live parent disconnect failed")
    close_error = RuntimeError("child close failed")

    class ParentSignal:
        def __init__(self, native):
            self.native, self.slots = native, []
            self.mode = "success"

        def connect(self, slot):
            result = self.native.connect(slot)
            self.slots.append(slot)
            return result

        def disconnect(self, slot):
            if self.mode == "error":
                raise disconnect_error
            if self.mode == "refuse":
                return False
            result = self.native.disconnect(slot)
            self.slots.remove(slot)
            return result

    class Parent(GUI.QWidget):
        def __init__(self):
            super().__init__()
            self.probe = ParentSignal(super().__getattribute__("destroyed"))

        def __getattribute__(self, name):
            if name == "destroyed":
                return object.__getattribute__(self, "probe")
            return super().__getattribute__(name)

    class Child(GUI.QWidget):
        def __init__(self, parent):
            super().__init__(parent)
            self.allow_observe = False
            self.native_destroyed = super().__getattribute__("destroyed")
            self.probe = NS(
                connect=self.connect_probe, disconnect=self.native_destroyed.disconnect
            )

        def __getattribute__(self, name):
            if name == "destroyed":
                return object.__getattribute__(self, "probe")
            return super().__getattribute__(name)

        def connect_probe(self, slot):
            if not self.allow_observe:
                raise primary
            return self.native_destroyed.connect(slot)

        def deleteLater(self):
            raise cleanup

        def close(self):
            if close_result == "error":
                raise close_error
            return False

    parent = Parent()
    child = Child(parent)
    with pytest.raises(ExceptionGroup) as caught:
        widgets.OwnedWidget(child, child, parent=parent)
    assert caught.value.exceptions == (primary, cleanup)
    owner = caught.value.owner
    assert len(parent.probe.slots) == 1
    fallback_slot = parent.probe.slots[0]
    child.allow_observe = True
    if close_result == "error":
        with pytest.raises(RuntimeError) as closed:
            owner.close()
        assert closed.value is close_error
    else:
        assert owner.close() is False
    assert owner._observed and owner.widget is child and valid(parent)
    parent.probe.mode = parent_disconnect
    GUI.QWidget.deleteLater(child)
    drain()
    assert not valid(child) and valid(parent) and owner.closed and owner.widget is None
    if parent_disconnect == "success":
        assert not parent.probe.slots
    else:
        assert parent.probe.slots == [fallback_slot]
        records = list(owner._connections)
        if getattr(owner, "_parent_connection", None) is not None:
            records.append(owner._parent_connection)
        assert any(
            signal is parent.probe and slot == fallback_slot for signal, slot in records
        ), (
            "A live parent callback must stay exactly reachable after independent child destruction"
        )
        assert (
            owner.last_error is disconnect_error
            if parent_disconnect == "error"
            else "refused" in str(owner.last_error)
        )
        if finish == "retry":
            parent.probe.mode = "success"
            owner.close()
            assert not parent.probe.slots
    parent.deleteLater()
    drain()
    owner.close()
    assert not getattr(owner, "_parent_connection", None) and not owner._connections


@pytest.mark.parametrize("redock", [False, True])
def test_panel_when_hidden_main_has_updates_disabled_then_floating_dock_paints(
    binding, redock
):
    # FontLab 9 keeps MainWindow hidden with updatesEnabled False; a dock created
    # under it inherits that, so the floating panel painted blank (Issue 250).
    main = GUI.QMainWindow()
    main.setUpdatesEnabled(False)
    owner = widgets.create_panel(main, "Owned dock", None, "right")
    dock = owner.widget
    try:
        if redock:
            dock.setFloating(False)  # docking again must restore painting too
            drain()
        assert dock.isFloating(), "dock in a hidden MainWindow floats"
        assert dock.updatesEnabled(), "floating dock must paint (updatesEnabled True)"
        assert owner.content.updatesEnabled(), "panel content must paint"
        assert not main.updatesEnabled(), "MainWindow updates state is left alone"
    finally:
        owner.close()
        main.deleteLater()
        drain()


@pytest.mark.parametrize(
    ("is_window", "enabled", "expected"),
    [(True, False, [True]), (True, True, []), (False, False, [])],
)
def test_enable_floating_updates_when_pythonqt_property_then_only_disabled_windows_change(
    is_window, enabled, expected
):
    # PythonQt exposes updatesEnabled as a plain value, not a method.
    calls = []
    dock = NS(
        isWindow=lambda: is_window, updatesEnabled=enabled, setUpdatesEnabled=calls.append
    )
    widgets._enable_floating_updates(dock)
    assert calls == expected, "only a floating dock with updates disabled is re-enabled"
