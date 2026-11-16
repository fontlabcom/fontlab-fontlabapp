# this_file: src/fontlabapp/fontui/glyph_row_table.py
# SPDX-License-Identifier: Apache-2.0
"""Shared report tab that lists one glyph per row and selects glyphs from it.

What: a ``SnapshotAuditTab`` whose rows come from ``report.rows`` (first column
is the glyph name). Select glyphs selects the chosen rows, or every listed
glyph when none is chosen; a double-click selects just that row's glyph. It
never edits outlines. The report text is still filled (tests read it) but
hidden; the table is the one visible result list.
"""

from typing import Any

from PythonQt import QtCore, QtGui

from .snapshot_audit import SnapshotAuditTab

STALE = "Refresh the report with an open font first."
RED = "#d33"
_HINT = "Double-click a row to select its glyph."


class GlyphTableTab(SnapshotAuditTab):
    """Report text, a glyph table and a Select glyphs button."""

    HEADERS: tuple[str, ...] = ()
    RED_COLUMN: int | None = None
    RIGHT_COLUMNS: tuple[int, ...] = ()

    def cells(self, row: tuple) -> list[str]:
        """Display cells of one report row; subclasses override."""
        return [str(value) for value in row]

    def is_red(self, row: tuple) -> bool:
        """Whether the red column of ``row`` is highlighted."""
        return False

    def pick(self, report: Any, names: list[str] | None) -> list:
        """Select ``names`` (every listed glyph when None) in the scanned font."""
        raise NotImplementedError

    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        self.table = QtGui.QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(list(self.HEADERS))
        self.table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
        self.hint = QtGui.QLabel(_HINT)
        self.layout.addWidget(self.hint)
        self.output.hide()  # the table shows the same rows; one list, not two
        self.layout.addWidget(self.table, 1)
        self.select_button = QtGui.QPushButton("Select glyphs")
        self.select_button.setEnabled(False)
        self.layout.addWidget(self.select_button)
        self.connect(self.select_button.clicked, lambda *a: self.select())
        self.connect(self.table.cellDoubleClicked, lambda row, *a: self.select([row]))

    def refresh(self) -> None:
        super().refresh()
        rows = list(self.report.rows) if self.report else []
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, text in enumerate(self.cells(row)):
                item = QtGui.QTableWidgetItem(text)
                if c == self.RED_COLUMN and self.is_red(row):
                    item.setForeground(QtGui.QBrush(QtGui.QColor(RED)))
                if c in self.RIGHT_COLUMNS:
                    item.setTextAlignment(int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter))
                self.table.setItem(r, c, item)
        self.select_button.setEnabled(bool(rows))

    def chosen_rows(self) -> list[int]:
        """Indices of the highlighted table rows."""
        return sorted({index.row() for index in self.table.selectionModel().selectedRows(0)})

    def select(self, rows: list[int] | None = None) -> None:
        """Select the glyphs of ``rows`` (default: highlighted rows, else all)."""
        if self.report is None:
            self.shell.set_status(STALE)
            return
        rows = self.chosen_rows() if rows is None else rows
        try:
            names = self.pick(self.report, [self.report.rows[r][0] for r in rows] if rows else None)
        except (ValueError, RuntimeError) as error:
            self.shell.set_status(str(error))
            return
        self.shell.set_status(f"Selected {len(names)} glyph{'s' if len(names) != 1 else ''}.")
