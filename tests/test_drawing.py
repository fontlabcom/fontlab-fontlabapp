# this_file: tests/test_drawing.py
"""Overlay callback/resize/transform/cleanup and owned-widget failure boundaries."""

import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from fontlabapp.qt.painting.drawing import Drawing
from fontlabapp.qt.widgets import create_widget


class Signal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)

    def disconnect(self, callback):
        self.callbacks.remove(callback)

    def emit(self):
        for callback in self.callbacks[:]:
            callback()


class Widget:
    def __init__(self, parent=None):
        self.parent_widget = parent
        self.destroyed = Signal()
        self.rect = SimpleNamespace(width=lambda: 80, height=lambda: 60)
        for name in (
            "setObjectName",
            "setAttribute",
            "setGeometry",
            "installEventFilter",
            "removeEventFilter",
            "show",
            "raise_",
            "update",
            "hide",
            "deleteLater",
            "close",
        ):
            setattr(self, name, Mock())


class Point:
    def __init__(self, x, y):
        self._x, self._y = x, y

    def x(self):
        return self._x

    def y(self):
        return self._y


@pytest.fixture
def qt(monkeypatch):
    painter = Mock()
    timer = Mock()
    timer.timeout = Signal()
    qt = SimpleNamespace(
        QtGui=SimpleNamespace(
            QWidget=Widget, QPainter=Mock(return_value=painter), QTransform=Mock()
        ),
        QtCore=SimpleNamespace(
            QPointF=Point,
            QEvent=SimpleNamespace(Resize=14),
            QTimer=Mock(return_value=timer),
            Qt=SimpleNamespace(WA_TransparentForMouseEvents=1, WA_NoSystemBackground=2),
        ),
    )
    monkeypatch.setitem(sys.modules, "PythonQt", qt)
    return qt


def test_overlay_paints_real_callback_resizes_and_removes_only_its_child(qt):
    parent = Widget()
    callback = Mock()
    drawing = Drawing(parent, callback)
    child = drawing.widget
    child.paintEvent(None)
    callback.assert_called_once_with(qt.QtGui.QPainter.return_value)
    qt.QtGui.QPainter.return_value.end.assert_called_once()
    child.eventFilter(parent, SimpleNamespace(type=lambda: 14))
    assert child.setGeometry.call_args.args == (parent.rect,)
    drawing.close()
    drawing.close()
    parent.removeEventFilter.assert_called_once_with(child)
    parent.close.assert_not_called()
    child.hide.assert_called_once()
    child.deleteLater.assert_called_once()
    assert (
        not parent.destroyed.callbacks
        and not qt.QtCore.QTimer.return_value.timeout.callbacks
    )
    with pytest.raises(RuntimeError, match="closed"):
        drawing.refresh()


def test_canvas_transform_fresh_each_paint_and_callback_failure_is_safe(qt):
    scale = [3]
    canvas = SimpleNamespace(
        mapToViewportF=lambda p: Point(p.x() * scale[0] + 7, -p.y() * scale[0] + 8),
        viewPoint=Point(0, 0),
        scale=lambda: scale[0],
    )
    drawing = Drawing(Widget(), lambda p: None, canvas=canvas)
    drawing.widget.paintEvent(None)
    assert qt.QtGui.QTransform.call_args.args == (3, 0, 0, -3, 7, 8)
    scale[0] = 5
    drawing._refresh_if_changed()
    drawing.widget.paintEvent(None)
    assert qt.QtGui.QTransform.call_args.args == (5, 0, 0, -5, 7, 8)
    drawing._callback = Mock(side_effect=ValueError("bad draw"))
    drawing.widget.paintEvent(None)
    with pytest.raises(RuntimeError, match="callback"):
        drawing.raise_if_failed()
    assert qt.QtGui.QPainter.return_value.end.call_count == 3
    drawing.close()


def test_parent_destruction_marks_overlay_closed_without_touching_deleted_objects(qt):
    parent = Widget()
    drawing = Drawing(parent, lambda p: None)
    parent.destroyed.emit()
    assert drawing.closed and drawing.widget is None
    drawing.close()


def test_owned_composition_build_failure_cleans_up(qt):
    parent = Widget()
    created = []

    def fail(widget):
        created.append(widget)
        raise ValueError("build failed")

    with pytest.raises(ValueError, match="build failed"):
        create_widget(parent, fail)
    created[0].deleteLater.assert_called_once()
    parent.close.assert_not_called()


@pytest.mark.parametrize("step", range(6))
@pytest.mark.parametrize("destroy_parent", [False, True])
def test_close_when_native_step_fails_then_retries_or_parent_destruction_clears(
    qt, step, destroy_parent
):
    parent, callback = Widget(), Mock()
    drawing = Drawing(parent, callback)
    child, timer = drawing.widget, drawing._timer
    targets = [
        (timer, "stop"),
        (timer.timeout, "disconnect"),
        (parent, "removeEventFilter"),
        (child, "hide"),
        (parent.destroyed, "disconnect"),
        (child, "deleteLater"),
    ]
    owner, name = targets[step]
    original, attempts = getattr(owner, name), []

    def fail_once(*args):
        attempts.append(args)
        if len(attempts) == 1:
            raise RuntimeError(f"cleanup step {step}")
        return original(*args)

    setattr(owner, name, Mock(side_effect=fail_once))
    with pytest.raises(RuntimeError, match=f"cleanup step {step}"):
        drawing.close()
    assert drawing.closed and drawing.widget is child
    child.paintEvent(None)
    child.eventFilter(parent, SimpleNamespace(type=lambda: 14))
    timer.timeout.emit()
    callback.assert_not_called()
    if destroy_parent:
        parent.destroyed.emit()
        assert drawing.widget is None and drawing._timer is None
        drawing.close()
        assert len(attempts) == 1, "Retried cleanup through a destroyed native wrapper"
    else:
        drawing.close()
        assert len(attempts) == 2, "Skipped the failed native cleanup step"
        assert drawing.widget is None and drawing._parent is None
        assert not parent.destroyed.callbacks and not timer.timeout.callbacks
        assert child.deleteLater.call_count == (2 if step == 5 else 1)
        assert timer.stop.call_count == (2 if step == 0 else 1)
        assert parent.removeEventFilter.call_count == (2 if step == 2 else 1)
        assert child.hide.call_count == (2 if step == 3 else 1)
        if step > 1:
            assert not timer.timeout.callbacks, "Repeated a completed disconnect"


def test_context_manager_closes_and_invalid_callback_is_rejected(qt):
    with pytest.raises(TypeError, match="callable"):
        Drawing(Widget(), None)
    with Drawing(Widget(), Mock()) as drawing:
        drawing.widget.eventFilter(Widget(), SimpleNamespace(type=lambda: 0))
    assert drawing.closed and drawing.widget is None


def test_close_when_parent_observer_cannot_be_restored_then_refuses_unsafe_retry(qt):
    parent = Widget()
    drawing = Drawing(parent, Mock())
    child = drawing.widget
    child.deleteLater.side_effect = RuntimeError("delete failed")
    parent.destroyed.connect = Mock(side_effect=RuntimeError("observer failed"))
    with pytest.raises(RuntimeError, match="parent destruction observer failed"):
        drawing.close()
    assert drawing.closed and drawing.widget is child
    with pytest.raises(RuntimeError, match="cannot safely retry"):
        drawing.close()
    child.deleteLater.assert_called_once()
    parent.destroyed.connect.assert_called_once()
    drawing._parent_destroyed()
    drawing.close()
    assert drawing.widget is None
