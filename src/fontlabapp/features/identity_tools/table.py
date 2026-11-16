# this_file: src/fontlabapp/features/identity_tools/table.py
# SPDX-License-Identifier: Apache-2.0
"""Native feature tables retain source identities when users sort numeric cells."""
from typing import Any


def selected_row(dialog: Any) -> int:
    """Resolve the selected unique source key rather than a visual row number."""
    item = dialog.table.item(dialog.table.currentRow(), 0)
    if item is None:
        return -1
    value = item.text
    key = value() if callable(value) else value
    return next((index for index, row in enumerate(dialog.rows) if str(row[0]) == key), -1)


def fill(dialog: Any, rows: list[tuple]) -> None:
    """Populate under blocked signals, restore source selection and allow resizing."""
    from fontlabapp import _native

    qt = _native('PythonQt')
    table = dialog.table
    selected = selected_row(dialog) if isinstance(getattr(dialog, 'rows', None), list) else -1
    key = dialog.rows[selected][0] if selected >= 0 else None
    table.blockSignals(True)
    table.setSortingEnabled(False)
    try:
        dialog.rows = rows
        table.setRowCount(len(rows))
        table.horizontalHeader().setSectionResizeMode(qt.QtGui.QHeaderView.Interactive)
        for row, cells in enumerate(rows):
            for column, value in enumerate(cells):
                item = qt.QtGui.QTableWidgetItem()
                item.setData(qt.QtCore.Qt.DisplayRole, value)
                table.setItem(row, column, item)
            if cells[0] == key:
                table.selectRow(row)
    finally:
        table.setSortingEnabled(True)
        table.blockSignals(False)
