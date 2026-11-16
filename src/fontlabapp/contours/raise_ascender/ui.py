# this_file: src/fontlabapp/contours/raise_ascender/ui.py
# SPDX-License-Identifier: MIT AND Apache-2.0
"""Original two-action Amount workflow with owned nonmodal Qt lifetime."""

import sys
from typing import Any

from fontlabapp import _native
from fontlabapp.core.edit_guards import append_note
from fontlabapp.core.signals.scope import Scope
from fontlabapp.qt.properties import value
from fontlabapp.contours.raise_ascender.native import Backend
from fontlabapp.core.completion import install
from fontlabapp.core.scripting import close_script_dialog, show_script_dialog

KEY = "raise_ascender"


def dialog_type(qt: Any = None) -> type:
    """Bind PythonQt lazily; real Qt can be injected for owned-widget controls."""
    qt = _native("PythonQt") if qt is None else qt
    core, gui = qt.QtCore, qt.QtGui

    class Dialog(gui.QDialog):
        """Original amount/default action; actions read current selection on click."""

        def __init__(self, parent: Any = None, *, backend: Any = None) -> None:
            gui.QDialog.__init__(self, parent)
            self._closed = self._dead = self._busy = self._closing = False
            self._ui_retired = False
            self._connections = []
            self.pending_disclosure = {"pending_updates": (), "pending_note": ""}
            self.backend = Backend() if backend is None else backend
            self.signals = Scope(self.failure)
            self._completion_lifetime = install(self, KEY)
            self._completion_lifetime.on_destroyed.append(self.destroyed_owned)
            try:
                self.setWindowFlags(
                    core.Qt.Tool
                    | core.Qt.WindowStaysOnTopHint
                    | core.Qt.WindowTitleHint
                    | core.Qt.WindowCloseButtonHint
                )
                self.setWindowTitle("Raise ascender")
                self.resize(360, 210)
                root = gui.QVBoxLayout(self)
                help_text = gui.QLabel(
                    "Move every own path node above its associated master’s x-height + 10. Controls are included."
                )
                help_text.setWordWrap(True)
                root.addWidget(help_text)
                form = gui.QFormLayout()
                self.amount = gui.QLineEdit("10")
                form.addRow("Amount", self.amount)
                root.addLayout(form)
                self.go_this = gui.QPushButton("Raise this master")
                self.go_all = gui.QPushButton("Raise all masters")
                self.go_this.setDefault(True)
                for button, callback in (
                    (self.go_this, lambda: self.apply(False)),
                    (self.go_all, lambda: self.apply(True)),
                ):
                    root.addWidget(button)
                    self.signals.connect(
                        button.clicked, lambda *args, callback=callback: callback()
                    )
                self.status = gui.QLabel(
                    "This master: every selected occurrence. All masters: every foreground layer of the first selected glyph."
                )
                self.status.setTextFormat(core.Qt.PlainText)
                self.status.setWordWrap(True)
                root.addWidget(self.status)
                self.close_button = gui.QPushButton("Close")
                root.addWidget(self.close_button)
                self.signals.connect(
                    self.close_button.clicked,
                    lambda *args: self.close(),
                    closing=True,
                    retry=True,
                )
            except BaseException:
                if self.close() is False:
                    sys.__dict__.setdefault("_fontlab_samples", {})[KEY] = self
                raise

        def apply(self, all_layers: bool) -> None:
            """No editing occurs until the backend preflights the complete action."""
            if self._closed or self._busy:
                return
            self._busy = True
            self.pending_disclosure = {"pending_updates": (), "pending_note": ""}
            try:
                result = self.backend.execute(
                    value(self.amount, "text"), all_layers, disclosure=self.pending_disclosure
                )
            finally:
                self._busy = False
            if not self._closed:
                self.status.setText(
                    append_note(
                        f"Moved {result['nodes']} nodes across {result['occurrences']} occurrences; {result['undo_steps']} Undo steps.",
                        self.pending_disclosure,
                    )
                )

        def failure(self, error: Exception) -> None:
            """Keep partial-write/Undo diagnosis visible; never report failed success."""
            self.slot_error = repr(error)
            if not self._dead and not self._ui_retired:
                self.status.setText(append_note("Error: " + str(error), self.pending_disclosure))

        def destroyed_owned(self) -> None:
            """Make retained callbacks inert without touching dying Qt emitters."""
            self._closed = self._dead = True
            self.signals.finish(destroyed=True)

        def reject(self) -> None:
            """Escape follows exactly the owned close path."""
            if self._closing:
                gui.QDialog.reject(self)
            elif not self._closed:
                self.close()

        def closeEvent(self, event: Any) -> None:
            """Disconnect all own signals before deferring widget destruction."""
            if self._busy:
                event.ignore()
                return
            self._closed = True
            if not self.signals.finish():
                event.ignore()
                return
            self._closing = True
            try:
                close_script_dialog(self, event, KEY)
                self._ui_retired = True
            except BaseException:
                # A failed helper may already have stopped terminal tracking.
                # The still-live panel must retain diagnosis and destruction.
                if self._completion_lifetime.closed:
                    self._completion_lifetime = install(self, KEY)
                    self._completion_lifetime.on_destroyed.append(self.destroyed_owned)
                raise
            finally:
                self._closing = False

    return Dialog


def show() -> Any:
    """Publish one registered replacement-safe modeless window."""
    return show_script_dialog(dialog_type(), KEY)
