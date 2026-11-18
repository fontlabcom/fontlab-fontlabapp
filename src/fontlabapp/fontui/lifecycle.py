# this_file: src/fontlabapp/fontui/lifecycle.py
# SPDX-License-Identifier: Apache-2.0
"""Owned widget lifetime and exact signal adapters."""

from PythonQt import QtGui
from weakref import ref as _ref

from fontlabapp.qt.compact import compact_layout


class Owned:
    """Owned top-level widget; its root layout is compact (6 px / 4 px) unless ``compact=False``."""

    def __init__(self, parent, *, compact=True):
        self.closed = False
        self.connections = []
        self.destroying = False
        self._closing = self._close_complete = self._child_closed = False
        self._hidden = self._delete_scheduled = self._parent_dead = False
        self._close_error = None
        self._own_observer = self._parent_observer = None
        owner_ref = _ref(self)

        class Root(QtGui.QWidget):
            def closeEvent(self, event):
                owner = owner_ref()
                if owner is None:
                    event.accept()
                    return
                try:
                    owner.close()
                except BaseException as error:
                    owner._close_error = error
                    event.ignore()
                else:
                    event.accept()

        self.widget = Root(parent)
        self.layout = QtGui.QVBoxLayout(self.widget)
        if compact:
            compact_layout(self.layout)  # FontLab panel metrics, issue 253
        self.connect(self.widget.destroyed, lambda *args: self._destroyed(), closing=True)
        self._own_observer = self.connections[-1]
        if parent is not None:
            self.connect(parent.destroyed, lambda *args: self._parent_destroyed(), closing=True)
            self._parent_observer = self.connections[-1]

    def _destroyed(self):
        self.destroying = True
        if not self.closed and not self._closing:
            try:
                self.close()
            except BaseException as error:
                self._close_error = error

    def _parent_destroyed(self):
        self._parent_dead = True
        if not self.closed and not self._closing:
            try:
                self.close()
            except BaseException as error:
                self._close_error = error

    def connect(self, signal, callback, *, closing=False):
        if self.closed and not closing:
            raise RuntimeError("Owned widget is closed")

        def slot(*args, **kwargs):
            if closing or not self.closed:
                return callback(*args, **kwargs)

        if signal.connect(slot) is False:
            raise RuntimeError("Owned signal connection refused")
        self.connections.append((signal, slot))

    def close(self):
        return self._close_with_child()

    def _close_with_child(self, child=None):
        """Resume this fixed owner without replaying acknowledged teardown."""
        self.closed = True
        if self._closing:
            self._close_error = RuntimeError("Owned cleanup is already in progress")
            raise self._close_error
        if self._close_complete:
            return
        self._closing = True
        try:
            if not self._child_closed:
                if child is not None:
                    child.close()
                    if not child._close_complete:
                        raise RuntimeError("Child cleanup is incomplete; owner retained")
                self._child_closed = True
            for pair in reversed(tuple(self.connections)):
                if pair is self._own_observer or pair is self._parent_observer:
                    continue
                signal, callback = pair
                if signal.disconnect(callback) is False:
                    raise RuntimeError("Owned signal disconnect refused")
                self.connections.pop(next(i for i, record in enumerate(self.connections) if record is pair))
            if not self.destroying:
                if not self._hidden:
                    if self.widget.hide() is False:
                        raise RuntimeError("Owned widget hide refused")
                    self._hidden = True
                if not self.destroying and not self._delete_scheduled:
                    if self.widget.deleteLater() is False:
                        raise RuntimeError("Owned widget deletion refused")
                    self._delete_scheduled = True
            for pair in reversed(tuple(self.connections)):
                dead = (pair is self._own_observer and self.destroying) or (pair is self._parent_observer and self._parent_dead)
                if not dead:
                    signal, callback = pair
                    if signal.disconnect(callback) is False:
                        raise RuntimeError("Owned observer disconnect refused")
                self.connections.pop(next(i for i, record in enumerate(self.connections) if record is pair))
                if pair is self._own_observer:
                    self._own_observer = None
                if pair is self._parent_observer:
                    self._parent_observer = None
            if self.connections or not self._child_closed or (not self.destroying and not (self._hidden and self._delete_scheduled)):
                raise RuntimeError("Owned cleanup is incomplete")
            self._close_complete = True
            self._close_error = None
        except BaseException as error:
            self._close_error = error
            raise
        finally:
            self._closing = False


HISTORY_ACTIONS = ("actionUndo", "actionRedo")


def follow_history(owner, callback):
    """Call callback after FontLab's Undo/Redo actions; return connections made.

    FontLab connects its own handlers first, so ours run after the history step.
    Outside FontLab (no fontlab module) nothing is connected. owner.close()
    disconnects these like every other owned connection.
    """
    try:
        import fontlab
    except ImportError:
        return 0
    window, count = fontlab.MainWindow(), 0
    for name in HISTORY_ACTIONS:
        action = window.findChild(QtGui.QAction, name) if window else None
        if action is not None:
            owner.connect(action.triggered, lambda *args: callback())
            count += 1
    return count


# flItems.qobject signals measured on FontLab 9.0.9783 (workspace
# verification/issue-106/evidence/issue-105/signal-probe1): glyph edits emit
# historyChanged + glyphUpdated(packageId, glyphId); Undo/Redo emit only
# historyIndexChanged; kerning edits only historyChanged; closing a document
# emits signalPackageClosed(flPackage).
CHANGE_SIGNALS = (
    "historyChanged",
    "historyIndexChanged",
    "glyphUpdated",
    "glyphsUpdated",
    "signalPackageClosed",
)
CHANGE_DELAY_MS = 100
UNFINISHED_EDITS = "glyph.incompleteContours"  # Fontport refuses invalidate() then
# Shared by every follower: while any follower's callback runs, signals it
# causes (directly or through another control) are not new external changes.
_REFRESHING = [0]
GLYPH_SIGNALS = frozenset(
    ("glyphUpdated", "glyphsUpdated")
)  # first argument: package id


def native_ids(fonts):
    """FontLab package ids of Fontport-backed fonts among fonts."""
    ids = (getattr(getattr(f, "_backend", None), "font_id", None) for f in fonts)
    return {i for i in ids if isinstance(i, int)}


def follow_changes(owner, callback, fonts, delay_ms=CHANGE_DELAY_MS):
    """Call callback after FontLab reports changes; return signals connected.

    Connected whenever FontLab is present (nothing outside it); fonts() is
    read at each signal, so an owner whose fonts appear later starts
    following then. Signals count only while fonts() holds a FontLab-backed
    font, and glyph(s)Updated only for those documents. The first signal arms
    a single-shot timer that later signals never restart, so callback runs at
    most delay_ms after the first change even under a steady stream. Signals
    emitted while any follower's callback runs (refresh reads or writes, also
    from other open controls) are ignored, no callback is re-entered, and a
    timer that fires during another follower's callback runs after it. Before
    it, each FontLab-backed (Fontport) font is refreshed, which drops its
    loaded glyph and layer handles. owner.close() disconnects everything; a
    pending timer then fires into nothing.
    """
    try:
        import fontlab
    except ImportError:
        return 0
    from PythonQt import QtCore

    items = fontlab.flItems.instance().qobject
    timer = QtCore.QTimer(owner.widget)
    timer.setSingleShot(True)
    timer.setInterval(delay_ms)
    state = {"pending": False}

    def arm():
        if _REFRESHING[0] or state["pending"] or not native_ids(fonts()):
            return
        state["pending"] = True
        timer.start()

    def fire(*args):
        state["pending"] = False
        if _REFRESHING[0] or getattr(owner, "closed", False):
            if _REFRESHING[0] and not getattr(owner, "closed", False):
                arm_later()
            return
        _REFRESHING[0] += 1
        unfinished = False
        try:
            for font in fonts():
                # Fontport has no change notifications
                # (glyph.externalChangeNotifications unsupported): drop its
                # loaded glyph/layer handles so the callback reads FontLab.
                # invalidate() (Fontport 1.1+) else refresh() (1.0).
                drop = getattr(font, "invalidate", None)
                if not callable(drop):
                    drop = getattr(font, "refresh", None)
                if callable(drop) and native_ids([font]):
                    try:
                        drop()
                    except Exception as exc:  # noqa: BLE001 - e.g. a closed document
                        # A script is mid-way through point edits: keep its
                        # handles (never discard them); the next signal retries.
                        # Other errors: the control's own refresh shows them.
                        if getattr(exc, "capability", None) == UNFINISHED_EDITS:
                            unfinished = True
            callback()
            note = getattr(owner, "diagnostic", None)
            if unfinished and note is not None:
                note.setText(
                    f"{note.text} A font has unfinished script edits; its view updates when the script finishes."
                )
        finally:
            _REFRESHING[0] -= 1

    def arm_later():
        # Our timer fired inside another follower's callback: run after it.
        state["pending"] = True
        timer.start()

    def changed(*args):
        arm()

    def glyphs_changed(package_id, *args):
        if package_id in native_ids(fonts()):
            arm()

    owner.connect(timer.timeout, fire)
    count = 0
    for name in CHANGE_SIGNALS:
        signal = getattr(items, name, None)
        if signal is not None:
            owner.connect(signal, glyphs_changed if name in GLYPH_SIGNALS else changed)
            count += 1
    return count
