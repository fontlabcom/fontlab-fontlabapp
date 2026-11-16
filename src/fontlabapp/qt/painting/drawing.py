# this_file: src/fontlabapp/qt/painting/drawing.py
"""Removable Qt painting on real Preview/Glyph widgets, without font edits."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Self

from fontlabapp import _native
from fontlabapp.contours.affine import viewport_transform


class Drawing:
    """Transparent child overlay whose callback receives an active QPainter.

    Pixel coordinates use the parent's local device-independent coordinates.
    Canvas coordinates use flCanvas.mapToViewportF freshly at each paint. A
    small native timer requests an update only when native zoom/size changes;
    it never paints or calls update/repaint from paintEvent.
    Keep the handle alive and call close(), or use it as a context manager.
    """

    def __init__(
        self, parent: Any, callback: Callable[[Any], None], *, canvas: Any = None
    ) -> None:
        if not callable(callback):
            raise TypeError("Drawing callback must be callable")
        qt = _native("PythonQt")
        self._parent, self._callback, self._canvas = parent, callback, canvas
        self._closed, self._state, self.last_error = False, None, None
        self._cleanup_step = 0
        self._cleanup_error = None
        self.paint_count = 0
        owner = self

        class Overlay(qt.QtGui.QWidget):
            def paintEvent(self, event):
                owner._paint()

            def eventFilter(self, watched, event):
                if not owner.closed and event.type() == qt.QtCore.QEvent.Resize:
                    owner.refresh()
                return False

        self.widget = Overlay(parent)
        self.widget.setObjectName("fontlabappDrawing")
        self.widget.setAttribute(qt.QtCore.Qt.WA_TransparentForMouseEvents, True)
        self.widget.setAttribute(qt.QtCore.Qt.WA_NoSystemBackground, True)
        self.widget.setGeometry(parent.rect)
        parent.installEventFilter(self.widget)
        parent.destroyed.connect(self._parent_destroyed)
        self._timer = qt.QtCore.QTimer(self.widget)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._refresh_if_changed)
        self._timer.start()
        self.widget.show()
        self.widget.raise_()
        self.refresh()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @property
    def closed(self) -> bool:
        """Whether callbacks are disabled; failed close() still needs a retry."""
        return self._closed

    def _transform(self):
        qt = _native("PythonQt")
        return qt.QtGui.QTransform(
            *viewport_transform(self._canvas, qt.QtCore.QPointF)
        )

    def _paint(self):
        if self._closed:
            return
        painter = _native("PythonQt").QtGui.QPainter(self.widget)
        try:
            if self._canvas is not None:
                painter.setWorldTransform(self._transform(), False)
            self._callback(painter)
            self.paint_count += 1
            self.last_error = None
        except Exception as error:  # noqa: BLE001 - Qt callbacks cannot unwind into C++
            # Exceptions cannot unwind through Qt's C++ paint callback safely.
            self.last_error = error
        finally:
            painter.end()

    def raise_if_failed(self) -> None:
        """Propagate a callback failure at a safe Python boundary after capture."""
        if self.last_error is not None:
            raise RuntimeError("FontLab drawing callback failed") from self.last_error

    def refresh(self) -> None:
        if self._closed:
            raise RuntimeError("Drawing is closed")
        self.widget.setGeometry(self._parent.rect)
        self.widget.raise_()
        self.widget.update()

    def _refresh_if_changed(self):
        if self._closed:
            return
        rect = self._parent.rect
        state = (rect.width(), rect.height())
        if self._canvas is not None:
            point = self._canvas.viewPoint
            state += (self._canvas.scale(), point.x(), point.y())
        if state != self._state:
            self._state = state
            self.refresh()

    def _parent_destroyed(self, *args):
        # Qt destroys the child and its timer. Never dereference their wrappers
        # after native deletion; sever Python callbacks and ownership instead.
        self._closed = True
        self._cleanup_step = 6
        self._cleanup_error = None
        self._callback = self._canvas = self._parent = self._timer = self.widget = None

    def close(self) -> None:
        """Disable callbacks immediately and resume native teardown after failures."""
        if self.widget is None:
            return
        self._closed = True
        self._callback = self._canvas = None
        if self._cleanup_error is not None:
            raise self._cleanup_error
        while self._cleanup_step < 6:
            match self._cleanup_step:
                case 0:
                    self._timer.stop()
                case 1:
                    self._timer.timeout.disconnect(self._refresh_if_changed)
                case 2:
                    self._parent.removeEventFilter(self.widget)
                case 3:
                    self.widget.hide()
                case 4:
                    self._parent.destroyed.disconnect(self._parent_destroyed)
                case 5:
                    try:
                        self.widget.deleteLater()
                    except Exception:
                        self._restore_parent_observer()
                        raise
            self._cleanup_step += 1
        self._callback = self._canvas = self._parent = self._timer = self.widget = None

    def _restore_parent_observer(self) -> None:
        """Keep parent destruction observable when native deletion could not queue."""
        try:
            self._parent.destroyed.connect(self._parent_destroyed)
        except Exception as error:
            self._cleanup_error = RuntimeError(
                "Drawing cleanup cannot safely retry: parent destruction observer failed"
            )
            raise self._cleanup_error from error
        self._cleanup_step = 4
