# this_file: src/fontlabapp/fontui/table.py
# SPDX-License-Identifier: Apache-2.0
"""GlyphTable: the shared sortable, filterable glyph list of the studio apps.

What: an owned ``QTableView`` over a ``QStandardItemModel`` through a
``QSortFilterProxyModel``. Click a header to sort (numbers sort as numbers);
drag a header edge to resize a column; type in the filter box to keep only
rows that contain the text in any column. Selecting a row emits
``row_selected(glyph_name, layer)``; the shell connects it to its preview.

How: ``GlyphTable(columns)`` then ``set_rows([GlyphRow(name, layer, values)])``.
``layer_column=True`` shows the layer as the second column (so ``columns`` must
name it); by default the layer stays hidden and ``values`` fill the other columns.
``row_selected`` is a plain callback hub with ``connect``/``disconnect``, so an
``Owned`` owner can connect it with ``owner.connect`` and closing releases it.
"""

from collections.abc import Callable, Sequence
from typing import Any, NamedTuple

from PythonQt import QtCore, QtGui

from .lifecycle import Owned

FILTER_PLACEHOLDER = "Filter"


class GlyphRow(NamedTuple):
    """One table row: the glyph, its layer (or master) and the column values."""

    glyph_name: str
    layer: str | None
    values: tuple[Any, ...]


class Callbacks:
    """A Python signal: ``connect``/``disconnect`` slots, ``emit`` calls each in order."""

    def __init__(self) -> None:
        self.slots: list[Callable[..., Any]] = []

    def connect(self, slot: Callable[..., Any]) -> None:
        self.slots.append(slot)

    def disconnect(self, slot: Callable[..., Any]) -> None:
        self.slots.remove(slot)

    def emit(self, *args: Any) -> None:
        for slot in list(self.slots):
            slot(*args)


def _item(value: Any) -> Any:
    item = QtGui.QStandardItem()
    shown = value if isinstance(value, (int, float)) and not isinstance(value, bool) else str(value)
    item.setData(shown, QtCore.Qt.DisplayRole)
    item.setEditable(False)
    return item


class GlyphTable(Owned):
    """Owned sortable, resizable, filterable glyph table; see the module text."""

    def __init__(self, columns: Sequence[str], parent: Any = None, layer_column: bool = False):
        super().__init__(parent)
        self.columns = tuple(columns)
        self.layer_column = bool(layer_column)
        self.rows: list[GlyphRow] = []
        self.row_selected = Callbacks()
        self.filter_box = QtGui.QLineEdit(self.widget)
        self.filter_box.setPlaceholderText(FILTER_PLACEHOLDER)
        self.filter_box.setAccessibleName("Filter glyphs")
        self.model = QtGui.QStandardItemModel(0, len(self.columns), self.widget)
        self.model.setHorizontalHeaderLabels(list(self.columns))
        self.proxy = QtGui.QSortFilterProxyModel(self.widget)
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterKeyColumn(-1)
        self.proxy.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.view = QtGui.QTableView(self.widget)
        self.view.setModel(self.proxy)
        self.view.setSortingEnabled(True)
        self.view.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.view.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        self.view.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
        header = self.view.horizontalHeader()
        header.setSectionResizeMode(QtGui.QHeaderView.Interactive)
        header.setStretchLastSection(True)
        self.layout.addWidget(self.filter_box)
        self.layout.addWidget(self.view)
        self.connect(self.filter_box.textChanged, self.proxy.setFilterFixedString)
        self.connect(self.view.selectionModel().currentRowChanged, self._current_changed)

    def set_rows(self, rows: Sequence[GlyphRow]) -> None:
        """Replace every row; sorting and the filter stay as the user set them."""
        self.rows = [GlyphRow(*row) for row in rows]
        self.model.setRowCount(0)
        for row in self.rows:
            cells = [row.glyph_name, *(("" if row.layer is None else row.layer,) if self.layer_column else ()), *row.values]
            self.model.appendRow([_item(value) for value in cells])

    def _current_changed(self, current: Any, *args: Any) -> None:
        if self.closed or current is None or not current.isValid():
            return
        row = self.rows[self.proxy.mapToSource(current).row()]
        self.row_selected.emit(row.glyph_name, row.layer)

    def current_row(self) -> GlyphRow | None:
        """The row under the table's current index (sorting and filtering applied), or None."""
        index = None if self.closed else self.view.currentIndex()
        if index is None or not index.isValid():
            return None
        return self.rows[self.proxy.mapToSource(index).row()]

    def select(self, glyph_name: str, layer: str | None = None) -> bool:
        """Select the first visible row for ``glyph_name`` (and ``layer``); True if found."""
        for number, row in enumerate(self.rows):
            if row.glyph_name == glyph_name and (layer is None or row.layer == layer):
                index = self.proxy.mapFromSource(self.model.index(number, 0))
                if index.isValid():
                    self.view.setCurrentIndex(index)
                    return True
        return False

    def close(self) -> None:
        self.row_selected.slots.clear()
        super().close()
