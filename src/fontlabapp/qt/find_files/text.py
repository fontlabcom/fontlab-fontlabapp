# this_file: src/fontlabapp/qt/find_files/text.py
# SPDX-License-Identifier: Apache-2.0
"""Literal editable queries and native combo history, without shadow strings."""

from typing import Any

from fontlabapp.qt.literal_text import line_edit_type, read_text
from fontlabapp.qt.properties import value


def combo_type(qt: Any) -> type:
    """Retain the Python line setter at the public editable-combo boundary."""
    gui = qt.QtGui
    line_type = line_edit_type(qt)

    class QueryCombo(gui.QComboBox):
        def __init__(self, parent: Any = None) -> None:
            super().__init__(parent)
            self._literal_line = line_type(self)
            self.setLineEdit(self._literal_line)

        def lineEdit(self) -> Any:
            return self._literal_line

        def setEditText(self, text: str) -> None:
            if "\0" in text:
                self._literal_line.setText(text)
            else:
                gui.QComboBox.setEditText(self, text)

    return QueryCombo


def query(qt: Any, combo: Any) -> str:
    """Read the actual editor value, including a native QString reference."""
    return read_text(qt, value(combo, "currentText"))


def remember(qt: Any, combo: Any, text: str) -> None:
    """Append one absent query to the real model, preserving order and draft."""
    if any(
        read_text(qt, combo.itemText(i)) == text
        for i in range(int(value(combo, "count")))
    ):
        return
    if "\0" not in text:
        combo.addItem(text)
        return
    _append_literal(qt, combo, text)


def _append_literal(qt: Any, combo: Any, text: str) -> None:
    """Stage native Return insertion; transfer its native model MIME row.

    Only the unshown staging editor receives Return. The live combo's index,
    cursor, selection, undo stack and activation signals are untouched. Native
    Qt serializes the existing QString; it never re-enters as a Python string.
    """
    core, gui = qt.QtCore, qt.QtGui
    stage = combo_type(qt)()
    mime = None
    try:
        stage.setEditText(text)
        event = gui.QKeyEvent(
            core.QEvent.KeyPress, core.Qt.Key_Return, core.Qt.NoModifier
        )
        gui.QLineEdit.keyPressEvent(stage.lineEdit(), event)
        if int(value(stage, "count")) != 1 or read_text(qt, stage.itemText(0)) != text:
            raise RuntimeError("The literal query could not be staged in history.")
        model = stage.model()
        mime = model.mimeData([model.index(0, 0)])
        if not combo.model().dropMimeData(
            mime, core.Qt.CopyAction, int(value(combo, "count")), 0, core.QModelIndex()
        ):
            raise RuntimeError("The literal query could not be added to history.")
    finally:
        try:
            if mime is not None:
                mime.deleteLater()
                core.QCoreApplication.sendPostedEvents(mime, core.QEvent.DeferredDelete)
        finally:
            stage.deleteLater()
            core.QCoreApplication.sendPostedEvents(stage, core.QEvent.DeferredDelete)
