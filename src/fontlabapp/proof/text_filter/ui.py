# this_file: src/fontlabapp/proof/text_filter/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Modeless Text Simplifier with source controls and complete owned teardown.

Modified from Slobzheninov/Glyphs-Scripts Text Filter; see NOTICE. PythonQt lives
in QtGui. No original body, Cocoa/Vanilla module or application exec is used.
"""

from functools import partial
from typing import Any

import fontlabapp.proof.text_filter.controls as controls
import fontlabapp.proof.text_filter.settings as prefs
from fontlabapp.glyphs.names.ui import NamesDialog, QtCore
from fontlabapp.core.scripting import connect_guarded, current_package
from fontlabapp.proof.text_filter.model import KEY, SavedText, filter_text
from fontlabapp.proof.tabs.text import open_text_tab


class TextFilterDialog(NamesDialog):
    """Retain text independently of proof-tab failures and source-font changes."""

    def __init__(self, parent: Any = None, *, settings: Any = None) -> None:
        super().__init__(parent, "Text Simplifier", KEY)
        self._closed, self._filling, self._busy = False, True, False
        self.settings_error = ""
        self._settings = settings
        if settings is None:
            self._settings = QtCore.QSettings("FontLab", "ScriptTextFilter")
            self._settings.setFallbacksEnabled(False)
        source = current_package()
        self.source_id = None if source is None else source.id
        self._open_tab = partial(open_text_tab, expected_id=self.source_id)
        controls.build(self)
        try:
            self._fill(prefs.load(self._settings))
            geometry = self._settings.value("geometry", None)
            if geometry is not None and not self.restoreGeometry(geometry):
                raise ValueError("Saved window geometry is invalid.")
        except Exception as error:  # noqa: BLE001 - keep a diagnosed closable panel
            self.settings_error = str(error)
            self.status.setText("Saved text could not be loaded: " + str(error))
        self._filling = False
        for edit in (self.input_edit, self.output_edit, self.characters_edit):
            self._connect(edit.textChanged, self.save)
        for button, callback in (
            (self.simplify_button, self.simplify),
            (self.reset_button, self.reset),
            (self.close_button, self.close),
        ):
            self._connect(button.clicked, callback)
        self._completion_lifetime.on_destroyed.append(self._destroyed)

    def _connect(self, signal: Any, callback: Any) -> None:
        """Fence late callbacks and errors before any native widget access."""

        def guarded(*args: Any) -> None:
            if self._closed:
                return
            try:
                callback()
            except Exception as error:  # noqa: BLE001 - keep the native slot boundary safe
                self.slot_error = repr(error)
                if not self._closed:
                    self.status.setText(str(error))

        connect_guarded(self, signal, guarded)

    def _fill(self, state: SavedText) -> None:
        """Set complete text without autosaving intermediate initialization/reset."""
        self.input_edit.setPlainText(state.input)
        self.output_edit.setPlainText(state.output)
        self.characters_edit.setPlainText(state.characters)

    def save(self) -> None:
        """Persist all source strings; a save error leaves the visible text intact."""
        if self._closed or self._filling:
            return
        state = SavedText(
            self.input_edit.toPlainText(),
            self.output_edit.toPlainText(),
            self.characters_edit.toPlainText(),
        )
        try:
            prefs.save(self._settings, state)
            self.settings_error = ""
        except Exception as error:  # noqa: BLE001 - retain a usable editor on I/O failure
            self.settings_error = str(error)
            if not self._closed:
                self.status.setText("Text is not saved: " + str(error))

    def reset(self) -> None:
        """Keep input, restore output/character defaults, remove only those keys."""
        if self._closed or self._busy:
            return
        prefs.reset(self._settings)
        self._filling = True
        try:
            self._fill(SavedText(self.input_edit.toPlainText()))
        finally:
            self._filling = False
        self.settings_error = ""
        self.status.setText("Output and character set reset. Input retained.")

    def simplify(self) -> None:
        """Publish complete output before the optional, source-bound proof action."""
        if self._closed or self._busy:
            return
        self._busy = True
        try:
            output = filter_text(
                self.input_edit.toPlainText(), self.characters_edit.toPlainText()
            )
            self.output_edit.setPlainText(output)
            if self._closed:
                return
            if self.new_tab.isChecked():
                if self.source_id is None:
                    raise ValueError(
                        "Reopen this tool with a font to open a proof tab."
                    )
                self._open_tab(output)
            if not self._closed and not self.settings_error:
                self.status.setText(f"Kept {len(output)} characters.")
        finally:
            self._busy = False

    def _drop(self) -> None:
        """Release I/O/source callbacks without accessing any native child widget."""
        self._closed = True
        self._settings = self._open_tab = self.source_id = None

    def _destroyed(self) -> None:
        """Drop dead-emitter records; Qt already removed those connections."""
        self._connections.clear()
        self._drop()

    def closeEvent(self, event: Any) -> None:
        """Save only geometry, then disconnect every owned slot before deletion."""
        if not self._closed:
            try:
                self._settings.setValue("geometry", self.saveGeometry())
                prefs.sync(self._settings)
            except Exception as error:  # noqa: BLE001 - closing must still free all handles
                self.slot_error = repr(error)
            self._drop()
        super().closeEvent(event)
