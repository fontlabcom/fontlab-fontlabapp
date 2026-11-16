# this_file: src/fontlabapp/contours/nodes/duplicator/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Owned nonmodal diagnosis for the original empty-selection and skipped targets."""

from typing import Any

from fontlabapp import _native
from fontlabapp.core.scripting import (
    close_script_dialog,
    connect_guarded,
    show_script_dialog,
)


def show_result(result: dict) -> Any:
    """Show every skipped target without writing the user's Output panel."""
    qt = _native("PythonQt").QtGui

    class ResultDialog(qt.QDialog):
        """Read-only result with explicit protected native close dispatch."""

        def __init__(self, parent: Any = None) -> None:
            super().__init__(parent)
            self._connections, self._closing = [], False
            self.setWindowTitle("Node Duplicator")
            self.setModal(False)
            layout = qt.QVBoxLayout(self)
            text = (
                "No nodes selected. Please select one or more nodes to duplicate."
                if result["no_selection_message"]
                else f"Inserted {result['inserted']} nodes."
            )
            if result["skipped"]:
                text += " Skipped unavailable path/node indices:"
            if result.get("pending_note"):
                ids = ", ".join(str(value) for value in result["pending_updates"])
                text += f"\nQueued glyph ids: {ids}.\n{result['pending_note']}"
            label = qt.QLabel(text)
            label.setWordWrap(True)
            layout.addWidget(label)
            if result["skipped"]:
                output = qt.QPlainTextEdit()
                output.setReadOnly(True)
                output.setPlainText(
                    "\n".join(
                        f"Glyph {g}, layer {l}: path {p}, node {n}"
                        for g, l, p, n in result.get("skipped_labels", result["skipped"])
                    )
                )
                layout.addWidget(output)
            button = qt.QPushButton("Close")
            layout.addWidget(button)
            connect_guarded(self, button.clicked, lambda *args: self.close())

        def reject(self) -> None:
            if self._closing:
                qt.QDialog.reject(self)
            else:
                self.close()

        def closeEvent(self, event: Any) -> None:
            self._closing = True
            try:
                close_script_dialog(self, event, "node-duplicator-result")
            finally:
                self._closing = False

    return show_script_dialog(ResultDialog, "node-duplicator-result")
