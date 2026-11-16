# this_file: src/fontlabapp/glyphs/completion/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Own the complete glyph-name completion pair, snapshots and terminal routes."""

import sys
from html import escape
from time import monotonic
from types import SimpleNamespace
from typing import Any

from fontlabapp.glyphs.completion.controls import build as build_controls
from fontlabapp.glyphs.names.ui import NamesDialog, QtCore, QtGui
from fontlabapp.qt.completion.editor import CompletionEditor
from fontlabapp.glyphs.completion.model import vocabulary


def _connect_string(sender: Any, slot: Any) -> None:
    """Select PythonQt's QString overload explicitly; default overloads differ."""
    if sender.connect("activated(QString)", slot) is False:
        raise RuntimeError("Qt refused the completion signal connection.")


def _disconnect_string(sender: Any, slot: Any) -> None:
    if sender.disconnect("activated(QString)", slot) is False:
        raise RuntimeError("Qt refused the completion signal disconnection.")


class GlyphCompletionDialog(NamesDialog):
    """Keep the local draft through Refresh failures and font changes."""

    def __init__(self, parent: Any, capture: Any, *, official: bool = False) -> None:
        self.KEY = "glyph_completion_official" if official else "glyph_completion"
        super().__init__(
            parent,
            "Glyph Name Completion" + (" — Focus and Popup" if official else ""),
            self.KEY,
        )
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
        self.official, self._closed, self._capture = official, False, capture
        self.words: tuple[str, ...] = ()
        self.controls, self._legacy, self._disconnect_errors = None, [], []
        try:
            self._completion_lifetime.on_destroyed.append(
                lambda: self._dispose(destroyed=True)
            )
            self.setAttribute(QtCore.Qt.WA_QuitOnClose, False)
            self.subtitle.setText(
                "Draft glyph names from the current font. Type at least three characters, or press Ctrl+E. Refresh updates the vocabulary and keeps your draft."
            )
            self.status = QtGui.QLabel()
            self.status.setWordWrap(True)
            self.controls = CompletionEditor(
                SimpleNamespace(QtCore=QtCore, QtGui=QtGui),
                self,
                self._wire,
                self._unwire,
                self._failure,
                official=official,
            )
            build_controls(self, QtGui)
            if parent is not None:
                self._connect(parent.destroyed, lambda *args: self._dispose())
            self.resize(760, 540)
            self.refresh()
        except BaseException:
            if self.close() is False:
                sys.__dict__.setdefault("_fontlab_samples", {})[self.KEY] = self
                self.show()
            raise

    def _action(self, menu: Any, label: str, call: Any) -> None:
        action = QtGui.QAction(label, self)
        menu.addAction(action)
        self.menu_actions[label] = action
        self._connect(
            action.triggered, lambda *args: call(), closing=label in {"Exit", "Close"}
        )

    def _show_vocabulary(self) -> None:
        self.controls.widget.setToolTip("<p>" + escape(", ".join(self.words)) + "</p>")

    def _connect(self, signal: Any, call: Any, *, closing: bool = False) -> None:
        def guarded(*args: Any) -> None:
            if self._closed and not closing:
                return
            try:
                call(*args)
            except Exception as error:  # noqa: BLE001 - contain the owned Qt callback or teardown boundary
                self._failure(error)

        if signal.connect(guarded) is False:
            raise RuntimeError("Qt refused the owned signal connection.")
        self._connections.append((signal, guarded))

    def _wire(self, sender: Any, call: Any) -> Any:
        def guarded(word: Any) -> None:
            if not self._closed:
                try:
                    call(word)
                except Exception as error:  # noqa: BLE001 - contain the owned Qt callback or teardown boundary
                    self._failure(error)

        _connect_string(sender, guarded)
        self._legacy.append((sender, guarded))
        return guarded

    def _unwire(self, sender: Any, slot: Any) -> None:
        _disconnect_string(sender, slot)
        self._legacy.remove((sender, slot))

    def invalidate(self) -> None:
        self.words = ()
        if not self._closed and self.controls is not None:
            self.controls.clear()
            self.controls.widget.setToolTip("")

    def _failure(self, error: Exception) -> None:
        if not self._closed:
            try:
                self.invalidate()
            except Exception as cleanup_error:  # noqa: BLE001 - preserve the failed native owner for Close retry
                self._closed = True
                self.controls._closed = True
                self.status.setText("Use window Close to retry: " + str(cleanup_error))
                return
            self.status.setText(str(error))

    def refresh(self) -> None:
        if self._closed:
            return
        try:
            self.invalidate()
            deadline = monotonic() + 2.0
            words = vocabulary(self._capture(deadline=deadline), deadline=deadline)
            if self._closed:
                return
            self.controls.replace_words(words)
            if monotonic() >= deadline:
                raise TimeoutError("Glyph vocabulary scan expired; no partial result.")
            self.words = words
            self.status.setText(
                f"{len(words)} glyph names captured. Refresh after font changes. Draft text changes no font data."
            )
        except Exception as error:  # noqa: BLE001 - contain the owned Qt callback or teardown boundary
            self._failure(error)

    def _dispose(self, *, destroyed: bool = False) -> bool:
        if self._closed and self.controls is None and not self._connections:
            return True
        self._closed, self._capture, self.words = True, None, ()
        if self.controls is not None:
            try:
                self.controls.close(destroyed=destroyed)
            except Exception as error:  # noqa: BLE001 - contain the owned Qt callback or teardown boundary
                self._disconnect_errors.append(str(error))
                if not destroyed:
                    self.status.setText("Close failed; retry Close: " + str(error))
                    return False
            self.controls = None
        if not destroyed:
            failed = []
            for signal, slot in reversed(self._connections):
                try:
                    if signal.disconnect(slot) is False:
                        raise RuntimeError("Qt refused the owned signal disconnection.")
                except Exception as error:  # noqa: BLE001 - contain the owned Qt callback or teardown boundary
                    self._disconnect_errors.append(str(error))
                    failed.append((signal, slot))
            self._connections[:] = reversed(failed)
            if failed:
                self.status.setText(
                    "Use window Close to retry: " + self._disconnect_errors[-1]
                )
                return False
        self._connections.clear()
        self._legacy.clear()
        windows = getattr(sys, "_fontlab_samples", {})
        if windows.get(self.KEY) is self:
            windows.pop(self.KEY)
        return True

    def closeEvent(self, event: Any) -> None:
        if not self._dispose():
            event.ignore()
            return
        super().closeEvent(event)
