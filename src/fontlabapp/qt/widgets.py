# this_file: src/fontlabapp/qt/widgets.py
"""Small owned Qt compositions inspired by TypeRig's native widget patterns."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import logging
from typing import Any, Self
from uuid import uuid4

from fontlabapp import _native
from fontlabapp.qt.compact import compact as _compact
from fontlabapp.qt.properties import value


class OwnedWidget:
    """Own created UI, retaining failed cleanup and parent-destruction recovery."""

    def __init__(
        self, widget: Any, content: Any, *, main: Any = None, parent: Any = None
    ) -> None:
        self.widget, self.content, self._main = widget, content, main
        self.closed = self._closing = self._accepted = self._removed = False
        self._delete_scheduled = False
        self._connections = []
        self._parent_connection = None
        self.last_error = None
        self._observed = False
        try:
            self._observe()
        except BaseException as error:
            self._observation_failure(error, parent)

    def _observe(self):
        if self.widget.destroyed.connect(self._destroyed) is False:
            raise RuntimeError("Owned widget destruction observation refused")
        self._observed = True

    def _observation_failure(self, error, parent):
        # Nothing has been built/shown yet: schedule this allocation for deletion.
        try:
            self.widget.deleteLater()
        except BaseException as cleanup:
            errors = [error, cleanup]
            if parent is not None:
                try:
                    signal = parent.destroyed
                    if signal.connect(self._parent_destroyed) is False:
                        raise RuntimeError("Owned widget parent observation refused")
                    self._parent_connection = (signal, self._parent_destroyed)
                except BaseException as observation:
                    errors.append(observation)
            failure = BaseExceptionGroup(
                "Widget observation and cleanup failed", errors
            )
            failure.owner = self
            raise failure from None
        self._destroyed()
        raise error

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _destroyed(self, *args):
        self.closed = True
        self.widget = self.content = self._main = None
        self._connections.clear()
        try:
            self._disconnect_parent()
        except BaseException as error:
            # The child is dead; preserve this still-live parent callback for retry.
            self.last_error = error

    def _parent_destroyed(self, *args):
        self._parent_connection = None
        self._destroyed()

    def _disconnect_parent(self):
        if self._parent_connection is not None:
            signal, slot = self._parent_connection
            if signal.disconnect(slot) is False:
                raise RuntimeError("Owned widget parent disconnect refused")
            self._parent_connection = None

    def close(self) -> bool:
        """Honor refusal; retry unfinished stages without losing live wrappers."""
        if self.closed:
            self._disconnect_parent()
            return True
        if self._closing:
            return False
        if not self._observed:
            self._observe()
        self._closing = True
        try:
            return self._close_stages()
        finally:
            self._closing = False

    def _close_stages(self) -> bool:
        if not self._accepted:
            if self.widget.close() is False:
                return False
            if self.closed:
                return True
            self._accepted = True
        if self._main is not None and not self._removed:
            self._main.removeDockWidget(self.widget)
            self._removed = True
            if self.closed:
                return True
        while self._connections:
            signal, slot = self._connections[-1]
            if signal.disconnect(slot) is False:
                raise RuntimeError("Owned widget callback disconnect refused")
            if self.closed:
                return True
            self._connections.pop()
        self._disconnect_parent()
        if self.closed:
            return True
        if not self._delete_scheduled:
            self.widget.deleteLater()
            self._delete_scheduled = True
            if self.closed:
                return True
        if self.widget.destroyed.disconnect(self._destroyed) is False:
            raise RuntimeError("Owned widget destruction disconnect refused")
        self._destroyed()
        return True


def _cleanup_failure(owned, error):
    """Retire failed factories or expose the exact owner and both failures."""
    try:
        if owned.close() is False:
            raise RuntimeError("Owned widget refused factory failure cleanup")
    except BaseException as cleanup:
        failure = BaseExceptionGroup(
            "Widget setup and cleanup failed", [error, cleanup]
        )
        failure.owner = owned
        raise failure from None


_LOG = logging.getLogger(__name__)


def _compact_content(content):
    """Apply compact metrics; cosmetic, so a widget that cannot take them still opens."""
    try:
        _compact(content)
    except (AttributeError, RuntimeError, TypeError) as error:
        _LOG.warning("compact: %r left unchanged: %s", content, error)


def _build(owned, build, compact=True):
    if build is not None:
        build(owned.content)
    if compact:
        _compact_content(owned.content)  # FontLab panel metrics, issue 253


def _floating_priority(owned, qt):
    dock = owned.widget
    if owned.closed or owned._closing or owned._accepted or not dock.isFloating():
        return
    flags = dock.windowFlags()
    priority = qt.QtCore.Qt.WindowStaysOnTopHint
    if flags & priority:
        return
    visible = dock.isVisible()
    dock.setWindowFlags(flags | priority)
    if visible:
        dock.show()


def _enable_floating_updates(dock: Any) -> None:
    """Let a floating dock paint under a MainWindow with updates disabled.

    FontLab 9 keeps its hidden MainWindow at updatesEnabled False; a dock
    created under it inherits that and its floating window paints blank.
    Only the floating dock is changed; the MainWindow state is left alone.
    PythonQt exposes updatesEnabled as a value, PySide6 as a method.
    """
    if dock.isWindow() and not value(dock, "updatesEnabled"):
        dock.setUpdatesEnabled(True)


def create_panel(
    main: Any, title: str, build: Callable | None, area: str, *, compact: bool = True
) -> OwnedWidget:
    qt = _native("PythonQt")
    areas = {
        "left": qt.QtCore.Qt.LeftDockWidgetArea,
        "right": qt.QtCore.Qt.RightDockWidgetArea,
        "top": qt.QtCore.Qt.TopDockWidgetArea,
        "bottom": qt.QtCore.Qt.BottomDockWidgetArea,
    }
    if area not in areas:
        raise ValueError("Dock area must be left, right, top or bottom")
    dock = qt.QtGui.QDockWidget(title, main)
    owned = OwnedWidget(dock, dock, main=main, parent=main)
    try:
        dock.setObjectName("fontlabappPanel_" + uuid4().hex)
        owned.content = qt.QtGui.QWidget(dock)
        dock.setWidget(owned.content)
        _build(owned, build, compact)
        main.addDockWidget(areas[area], dock)
        # FontLab can keep MainWindow hidden; retain docking and parent identity.
        if not main.isVisible():
            dock.setFloating(True)
            _enable_floating_updates(dock)
        _floating_priority(owned, qt)

        def floating_changed(*args):
            try:
                # Docking into the hidden MainWindow would make the panel vanish
                # (e.g. a title-bar double-click); float it again once Qt has
                # finished the transition (re-floating inside the signal is undone).
                if args and not args[0] and not main.isVisible():
                    qt.QtCore.QTimer.singleShot(0, refloat)
                _floating_priority(owned, qt)
            except BaseException as error:
                # Qt signal dispatch must not lose the owner or escape into Qt.
                owned.last_error = error

        def refloat():
            try:
                if not owned.closed and not dock.isFloating() and not main.isVisible():
                    dock.setFloating(True)
                    _enable_floating_updates(dock)
                    dock.show()
            except BaseException as error:
                owned.last_error = error

        floating_signal = dock.topLevelChanged
        if floating_signal.connect(floating_changed) is False:
            raise RuntimeError("Owned widget floating priority connection refused")
        owned._connections.append((floating_signal, floating_changed))
        dock.show()
    except BaseException as error:
        _cleanup_failure(owned, error)
        raise
    return owned


def create_dialog(
    main: Any, title: str, build: Callable | None, *, compact: bool = True
) -> OwnedWidget:
    qt = _native("PythonQt")
    widget = qt.QtGui.QDialog(main)
    owned = OwnedWidget(widget, widget, parent=main)
    try:
        widget.setWindowTitle(title)
        widget.setModal(False)
        _build(owned, build, compact)
        widget.show()
    except BaseException as error:
        _cleanup_failure(owned, error)
        raise
    return owned


def create_widget(
    parent: Any,
    build: Callable | None,
    *,
    floating: bool = False,
    show: bool = True,
    compact: bool = True,
) -> OwnedWidget:
    qt = _native("PythonQt")
    widget = (
        qt.QtGui.QWidget(parent, qt.QtCore.Qt.Tool)
        if floating
        else qt.QtGui.QWidget(parent)
    )
    owned = OwnedWidget(widget, widget, parent=parent)
    try:
        _build(owned, build, compact)
        if show:
            widget.show()
    except BaseException as error:
        _cleanup_failure(owned, error)
        raise
    return owned


def release_owned(
    scope: Any, owned: Any, problems: list, closers: Sequence[Any] = ()
) -> bool:
    """Finish ``scope``, close ``closers`` then ``owned``; True only when all released.

    Stops at the first refusal so the window stays usable: a falsy
    ``scope.finish()``, a falsy ``owned.close()`` or a ``RuntimeError`` from
    any close, which is appended to ``problems``. Other errors propagate.
    Closer results are ignored; ``None`` closers and a ``None`` owned are
    skipped. The caller keeps its handle and reports when this returns False.
    """
    if not scope.finish():
        return False
    try:
        for closer in closers:
            if closer is not None:
                closer.close()
        return owned is None or bool(owned.close())
    except RuntimeError as error:
        problems.append(error)
        return False
