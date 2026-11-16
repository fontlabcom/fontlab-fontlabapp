# this_file: src/fontlabapp/features/editor/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Small feature-panel extension of the shared script shell.

FontLab's PythonQt supplies all controls; no external Qt runtime is imported.
Per-tool controls, computations and actions remain in Scriptmix. This lazy
module shares guarded callbacks, font binding and deferred Close destruction.
"""

from typing import Any

from fontlabapp import _native
from fontlabapp.fonts.info.ui import FontInfoDialog

QtCore, QtGui = _native("PythonQt").QtCore, _native("PythonQt").QtGui


class FeaturesDialog(FontInfoDialog):
    """Reuse the proven panel lifecycle with each tool's original content."""

    def safe(self, action: Any) -> Any:
        """Invalidate both Apply and independently copyable previews on failure."""
        try:
            return action()
        except Exception as error:  # noqa: BLE001 - contain native slot failures
            self._preview_valid = False
            self._copy_preview_valid = False
            self.status.setText(str(error))
            self.apply_button.setEnabled(False)

    def prepare(self) -> Any:
        """Create a content layout before the shared footer for tool controls."""
        self.font_data = _native("fontlab").CurrentFont() if self.package else None
        self.names = (
            sorted(g.name for g in self.font_data.glyphs) if self.font_data else []
        )
        self.last_result = None
        self.table.hide()
        self.setMinimumWidth(640)
        self.resize(780, 620)
        body = QtGui.QVBoxLayout()
        self.content.insertLayout(self.content.count() - 1, body, 1)
        return body

    def _safe(self, callback: Any) -> Any:
        """Preserve the archived callback interface with shared invalidation."""
        return self.safe(callback)

    def make_table(self, headers: list[str]) -> Any:
        """Create the original selectable, read-only feature result table."""
        table = QtGui.QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        table.horizontalHeader().setSectionResizeMode(QtGui.QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(
            0, QtGui.QHeaderView.ResizeToContents
        )
        return table

    def fill(self, rows: list[tuple]) -> None:
        """Retain original rows and render numeric counts with right alignment."""
        self.rows = rows
        self.table.setRowCount(len(rows))
        for row, cells in enumerate(rows):
            for column, value in enumerate(cells):
                item = QtGui.QTableWidgetItem(str(value))
                if isinstance(value, int):
                    item.setTextAlignment(
                        int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                    )
                self.table.setItem(row, column, item)

    def copy_text(self, text: str) -> None:
        """Copy the selected preview without changing font data."""
        self.ensure_font()
        if not (self._preview_valid or getattr(self, "_copy_preview_valid", False)):
            raise ValueError("No valid preview; refresh or reopen this tool.")
        QtGui.QApplication.clipboard().setText(text)
        self.last_result = {"copied": text}
        self.status.setText("Copied feature code to the clipboard.")
