# this_file: src/fontlabapp/glyphs/tree/editable/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Own both complete editable glyph-tree drafts without native font writers."""

import sys
from time import monotonic
from types import SimpleNamespace
from typing import Any

from fontlabapp import _native
from fontlabapp.qt.trees.editable.actions import Controller
from fontlabapp.qt.trees.editable.controls import build
from fontlabapp.qt.trees.editable.editor import Editor
from fontlabapp.core.signals.scope import Scope
from fontlabapp.core.completion import Completion
from fontlabapp.qt.trees.data import Tree, check_deadline

QtCore, QtGui = _native("PythonQt").QtCore, _native("PythonQt").QtGui


def _terminal(owner: Completion, signal: Any, call: Any) -> None:
    """Retain a terminal pair only after an explicitly successful connection."""
    if signal.connect(call) is False:
        raise RuntimeError("Qt refused the completion signal connection.")
    owner.hooks.append((signal, call))


class EditableGlyphTreeDialog(QtGui.QDialog):
    def __init__(self, parent: Any, capture: Any, *, official: bool = False) -> None:
        QtGui.QDialog.__init__(self, parent)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
        self.official, self._capture = official, capture
        self.KEY = "editable_glyph_tree" if official else "editable_glyph_outline"
        self._closed = self._destroyed = False
        self.editor, self._editors, self.last_error = None, [], ""
        self.scope = Scope(self._failure)
        self._completion_lifetime = Completion(self, self.KEY)
        self._completion_lifetime.on_destroyed.append(
            lambda: self._dispose(destroyed=True)
        )
        self.qt = SimpleNamespace(QtCore=QtCore, QtGui=QtGui)
        try:
            owner = self._completion_lifetime
            for signal, call in (
                (self.destroyed, lambda *args: owner.destroyed()),
                (self.finished, lambda *args: owner.complete()),
            ):
                _terminal(owner, signal, call)
            self.setAttribute(QtCore.Qt.WA_QuitOnClose, False)
            self.setWindowTitle(
                "Editable Glyph Tree" if official else "Editable Glyph Outline"
            )
            self.controller = Controller(self, self.qt)
            build(self, self.qt)
            self.resize(800, 620)
            self.refresh()
        except BaseException:
            if self.close() is False:
                sys.__dict__.setdefault("_fontlab_samples", {})[self.KEY] = self
                self.show()
            raise

    def _failure(self, error: Exception) -> None:
        self.last_error = str(error)
        if not self._destroyed and hasattr(self, "status"):
            try:
                self.status.setText(self.last_error)
            except Exception:  # noqa: BLE001 - never dereference a dead Qt label again
                self._destroyed = True

    def _selected(self, editor: Any) -> None:
        if not self._closed and editor is self.editor:
            self.controller.update()

    def _changed(self, editor: Any) -> None:
        if not self._closed and editor is self.editor and editor.model.edited:
            self.status.setText(
                "Local draft edited; no font data changed. Reset Draft discards these edits."
            )

    def refresh(self, *, discard: bool = False) -> None:
        if self._closed:
            return
        if self.editor is not None and self.editor.model.edited and not discard:
            self.status.setText(
                "Your local draft has edits. Use Reset Draft to load the current font."
            )
            return
        candidate = None
        try:
            deadline = monotonic() + 2.0
            snapshot = self._capture(deadline=deadline)
            if self._closed:
                return
            if not isinstance(snapshot, Tree):
                raise TypeError("Capture must return a complete immutable Tree.")
            candidate = Editor(self.qt, self, snapshot, deadline)
            if self._closed:
                candidate.close()
                return
            check_deadline(deadline)
            self.container.addWidget(candidate.view)
            if self.editor is not None and not self.editor.close():
                raise RuntimeError("Old editor cleanup failed; use Close to retry.")
            self.editor = candidate
            self._editors[:] = [e for e in self._editors if not e.released]
            candidate.view.show()
            self.controller.update(initial=True)
            roots = sum(parent == -1 for parent, _ in snapshot.rows)
            self.status.setText(
                f"{roots} glyphs; {len(snapshot.rows)} complete local rows. Edits change this draft only."
            )
        except Exception as error:  # noqa: BLE001 - preserve the current draft on failed reload
            self._failure(error)
            for editor in list(self._editors):
                if editor is not self.editor:
                    try:
                        editor.close()
                    except Exception as failure:  # noqa: BLE001 - retain unreturned failed owners
                        self._failure(failure)
            self._editors[:] = [e for e in self._editors if not e.released]
            if any(e.scope.closed and not e.released for e in self._editors):
                self._closed, self._capture, self.scope.closed = True, None, True
                for editor in self._editors:
                    if editor.view is not None:
                        editor.view.setEnabled(False)
                self._failure(
                    RuntimeError("Editor cleanup failed; use Close to retry.")
                )
            if not self._closed:
                self.controller.update(initial=True)

    def _dispose(self, *, destroyed: bool = False) -> bool:
        self._closed, self._destroyed, self._capture = True, destroyed, None
        self.scope.closed = True
        for editor in self._editors:
            try:
                if not editor.close(destroyed=destroyed):
                    self._failure(
                        RuntimeError("Editor disconnect failed; retry Close.")
                    )
                    return False
            except Exception as error:  # noqa: BLE001 - refuse deletion of a failed editor owner
                self._failure(error)
                return False
        self.editor, self._editors = None, []
        if not self.scope.finish(destroyed=destroyed):
            self._failure(RuntimeError("Signal disconnect failed; retry Close."))
            return False
        # Keep the destruction tombstone until all editor/control/retry signals
        # have drained. Disconnect finished first, destroyed last; stop on failure.
        if not destroyed:
            for signal, call in reversed(list(self._completion_lifetime.hooks)):
                try:
                    if signal.disconnect(call) is False:
                        raise RuntimeError(
                            "Qt refused the completion signal disconnection."
                        )
                except Exception as error:  # noqa: BLE001 - retain the terminal owner
                    self._failure(
                        RuntimeError("Use window Close to retry: " + str(error))
                    )
                    return False
                self._completion_lifetime.hooks.remove((signal, call))
        windows = getattr(sys, "_fontlab_samples", {})
        if windows.get(self.KEY) is self:
            windows.pop(self.KEY)
        return True

    def closeEvent(self, event: Any) -> None:
        if not self._dispose():
            event.ignore()
            return
        self._completion_lifetime.stop()
        QtGui.QDialog.closeEvent(self, event)
        self.deleteLater()
