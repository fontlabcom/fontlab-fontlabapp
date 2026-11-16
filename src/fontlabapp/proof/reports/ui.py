# this_file: src/fontlabapp/proof/reports/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Owned plain-text snapshots on the existing NamesDialog lifecycle."""

import json
import sys
from contextlib import suppress
from typing import Any

from fontlabapp.glyphs.names.ui import NamesDialog, QtGui
from fontlabapp.core.scripting import connect_guarded, show_script_dialog


class ReportDialog(NamesDialog):
    """Display detached values, with no active-font lookup or mutation callbacks."""

    def __init__(self, parent: Any, title: str, key: str, text: str) -> None:
        super().__init__(parent, title, key)
        self._released = False
        try:
            self.report = json.loads(text)
            self.setModal(False)
            self.subtitle.setText(
                "Detached snapshot. Close and run the lesson again to refresh."
            )
            self.editor = QtGui.QPlainTextEdit(self)
            self.editor.setReadOnly(True)
            self.editor.setPlainText(text)
            self.root.addWidget(self.editor)
            self.close_button = QtGui.QPushButton("Close", self)
            self.root.addWidget(self.close_button)
            connect_guarded(
                self,
                self.close_button.clicked,
                lambda *args: None if self._released else self.close(),
            )
            self._completion_lifetime.on_destroyed.append(self._release)
            if parent is not None:
                connect_guarded(self, parent.destroyed, lambda *args: self._release())
            self.resize(720, 520)
        except BaseException:
            self._release()
            self.deleteLater()
            raise

    def _release(self) -> None:
        """Disconnect plain Python callbacks before parent or dialog deletion."""
        if self._released:
            return
        self._released = True
        for signal, slot in self._connections:
            with suppress(Exception):
                signal.disconnect(slot)
        self._connections.clear()
        windows = getattr(sys, "_fontlab_samples", {})
        if windows.get(self._key) is self:
            windows.pop(self._key)

    def closeEvent(self, event: Any) -> None:
        """Release owned callbacks before the standard native close/deletion."""
        self._release()
        super().closeEvent(event)


def show(text: str, title: str, key: str) -> Any:
    """Use the common registry for replacement and native-window ownership."""
    created = []

    def build(parent: Any) -> ReportDialog:
        dialog = ReportDialog(parent, title, key, text)
        created.append(dialog)
        return dialog

    try:
        return show_script_dialog(build, key)
    except BaseException:
        for dialog in created:
            dialog._release()
            with suppress(Exception):
                dialog.close()
            dialog.deleteLater()
        raise
