# this_file: src/fontlabapp/qt/tables/items.py
# SPDX-License-Identifier: MIT
"""Injected Qt table text/checkbox items, retaining construction and handoff order.

Columns supply generic ``key``, ``cell_title``, ``checkbox`` and ``editable``
attributes. Callers own column interpretation, data, callbacks, quiet scopes,
selection and widget lifetime. Late getters keep native lookup at the original
point even when value conversion or callbacks replace a caller's widget.
No Qt binding or foreign compatibility package is imported.
"""
from collections.abc import Callable, Iterable, Mapping
from typing import Any


def cell_text(value: Any) -> str:
    """Keep missing values blank while retaining every other literal string."""
    return "" if value is None else str(value)


def item_flags(qt: Any, editable: bool) -> Any:
    """Set precisely selectable/enabled, adding editability only when requested."""
    flags = qt.ItemIsSelectable | qt.ItemIsEnabled
    return flags | qt.ItemIsEditable if editable else flags


def place_text(qt: Any, table: Callable[[], Any], row: int, column: int,
               value: Any, editable: bool) -> None:
    """Construct/configure a plain item before giving ownership to the table."""
    item = qt.QtGui.QTableWidgetItem("" if value is None else str(value))
    flags = qt.QtCore.Qt.ItemIsSelectable | qt.QtCore.Qt.ItemIsEnabled
    item.setFlags(flags | qt.QtCore.Qt.ItemIsEditable if editable else flags)
    table().setItem(row, column, item)


def fill_row(gui: Any, row: int, values: Mapping, columns: Iterable,
             flags: Callable[[], Callable[[bool], Any]], qt: Callable[[], Any],
             table: Callable[[], Any]) -> None:
    """Place all column occurrences; check state precedes flags and ownership.

    ``flags`` returns the caller's current flag policy. Its lookup precedes
    evaluating column editability, preserving virtual-method and failure order.
    Empty columns touch no native item, flags namespace or table.
    """
    for index, column in enumerate(columns):
        cell = gui.QTableWidgetItem(
            column.cell_title if column.checkbox else cell_text(values.get(column.key))
        )
        options = flags()(column.editable and not column.checkbox)
        if column.checkbox:
            native = qt()
            if column.editable:
                options |= native.ItemIsUserCheckable
            cell.setCheckState(native.Checked if values.get(column.key) else native.Unchecked)
        cell.setFlags(options)
        table().setItem(row, index, cell)
