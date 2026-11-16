# this_file: tests/test_fontui_weak_owner_callbacks.py
"""Real Qt dynamic owner callbacks retain live dispatch, not dead owners."""
import gc
import importlib
import weakref

import pytest
from test_fontui_master_width_comparison import actual_qt as _actual_qt_fixture
actual_qt = _actual_qt_fixture
del _actual_qt_fixture


def drain():
    from PySide6 import QtCore
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    gc.collect()


@pytest.mark.parametrize("error_type", [None, RuntimeError, ValueError, KeyboardInterrupt])
def test_root_close_when_live_then_exact_primary_error_or_accept(actual_qt, monkeypatch, error_type):
    from PySide6.QtGui import QCloseEvent
    module = importlib.import_module("fontlabapp.fontui.lifecycle")
    _, parent, _ = actual_qt
    owner = module.Owned(parent)
    calls = []
    error = error_type("owned close error") if error_type else None
    def close():
        calls.append(owner)
        if error:
            raise error
    with monkeypatch.context() as patch:
        patch.setattr(owner, "close", close)
        event = QCloseEvent()
        owner.widget.closeEvent(event)
        assert calls == [owner]
        assert event.isAccepted() is (error is None)
        if error:
            assert owner._close_error is error
    owner.close()
    assert owner._close_complete
    drain()


def test_root_close_when_last_external_reference_dropped_then_dispatch_holds_owner(actual_qt):
    from PySide6.QtGui import QCloseEvent
    from types import MethodType
    module = importlib.import_module("fontlabapp.fontui.lifecycle")
    _, parent, _ = actual_qt
    owner = module.Owned(parent)
    hold = [owner]
    reference = weakref.ref(owner)
    widget = owner.widget
    root_class = type(widget)
    def close(self):
        hold.clear()
        gc.collect()
        assert reference() is self
        module.Owned.close(self)
    owner.close = MethodType(close, owner)
    del owner
    event = QCloseEvent()
    widget.closeEvent(event)
    assert event.isAccepted()
    drain()
    assert reference() is None
    # The actual retained dynamic class no longer retains its former owner.
    orphan = root_class(parent)
    orphan.closeEvent(event)
    assert event.isAccepted()
    orphan.deleteLater()
    drain()


@pytest.mark.parametrize("resize", [False, True])
@pytest.mark.parametrize("dead", [False, True])
def test_scroll_event_when_live_or_dead_then_single_base_route(actual_qt, monkeypatch, resize, dead):
    from PySide6 import QtCore
    qt, parent, _ = actual_qt
    module = importlib.import_module("fontlabapp.fontui.sequence")
    owner = module.Sequence(None, parent)
    scroll = owner.scroll
    cls = type(scroll)
    reference = weakref.ref(owner)
    timer_calls, base_calls = [], []
    event = QtCore.QEvent(QtCore.QEvent.Resize if resize else QtCore.QEvent.User)
    if dead:
        owner.close()
        del owner, scroll
        drain()
        assert reference() is None
        scroll = cls(parent)
    else:
        monkeypatch.setattr(owner.reflow_timer, "start", lambda: timer_calls.append(True))
    def base(widget, received):
        base_calls.append((widget, received))
        return True
    with monkeypatch.context() as patch:
        patch.setattr(qt.QtGui.QScrollArea, "viewportEvent", base)
        assert scroll.viewportEvent(event) is True
        assert base_calls == [(scroll, event)]
        assert timer_calls == ([True] if resize and not dead else [])
        error = ValueError("base failure")
        def fail(*args):
            raise error
        patch.setattr(qt.QtGui.QScrollArea, "viewportEvent", fail)
        with pytest.raises(ValueError) as caught:
            scroll.viewportEvent(event)
        assert caught.value is error
    if not dead:
        owner.close()
    else:
        scroll.deleteLater()
    drain()


@pytest.mark.parametrize("dead", [False, True])
def test_canvas_events_when_owner_lifetime_changes_then_exact_paint_mouse_key_routing(actual_qt, monkeypatch, dead):
    from PySide6 import QtCore, QtGui
    qt, parent, _ = actual_qt
    module = importlib.import_module("fontlabapp.fontui.sequence_canvas")
    events = []
    class Owner:
        def select_at(self, x, y):
            events.append(("mouse", x, y))
        def select_key(self, key):
            events.append(("key", key))
            return key == QtCore.Qt.Key_Left
    owner = Owner()
    canvas = module.create_canvas(owner, parent)
    reference = weakref.ref(owner)
    if dead:
        del owner
        gc.collect()
        assert reference() is None
    monkeypatch.setattr(module, "paint", lambda target, widget: events.append(("paint", target, widget)))
    canvas.paintEvent(QtGui.QPaintEvent(QtCore.QRect(0, 0, 20, 20)))
    assert len(events) == (0 if dead else 1)
    if not dead:
        assert events.pop() == ("paint", owner, canvas)
    mouse = QtGui.QMouseEvent(QtCore.QEvent.MouseButtonPress, QtCore.QPointF(7, 9),
                             QtCore.Qt.LeftButton, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier)
    canvas.mousePressEvent(mouse)
    assert mouse.isAccepted() is (not dead)
    assert events == ([] if dead else [("mouse", 7, 9)])
    events.clear()
    bases = []
    def base(widget, event):
        bases.append((widget, event))
    with monkeypatch.context() as patch:
        patch.setattr(module.QtGui.QWidget, "keyPressEvent", base)
        for key in (QtCore.Qt.Key_Left, QtCore.Qt.Key_X):
            event = QtGui.QKeyEvent(QtCore.QEvent.KeyPress, key, QtCore.Qt.NoModifier)
            assert canvas.keyPressEvent(event) is None
            expected = (2 if dead else 1) if key == QtCore.Qt.Key_X else int(dead)
            assert len(bases) == expected
    if not dead:
        error = KeyboardInterrupt("mouse callback")
        def fail(*args):
            raise error
        monkeypatch.setattr(owner, "select_at", fail)
        mouse.ignore()
        with pytest.raises(KeyboardInterrupt) as caught:
            canvas.mousePressEvent(mouse)
        assert caught.value is error and not mouse.isAccepted()
    canvas.deleteLater()
    drain()


def test_canvas_when_dispatch_drops_owner_then_keeps_one_strong_local(actual_qt, monkeypatch):
    from PySide6 import QtCore, QtGui
    _, parent, _ = actual_qt
    module = importlib.import_module("fontlabapp.fontui.sequence_canvas")
    # A regular Python owner supports the same weak-reference contract as Sequence.
    class Owner:
        pass
    owner = Owner()
    hold = [owner]
    reference = weakref.ref(owner)
    canvas = module.create_canvas(owner, parent)
    def paint(target, widget):
        hold.clear()
        gc.collect()
        assert reference() is target and widget is canvas
    monkeypatch.setattr(module, "paint", paint)
    del owner
    canvas.paintEvent(QtGui.QPaintEvent(QtCore.QRect(0, 0, 10, 10)))
    gc.collect()
    assert reference() is None
    canvas.deleteLater()
    drain()
