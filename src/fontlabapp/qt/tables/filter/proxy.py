# this_file: src/fontlabapp/qt/tables/filter/proxy.py
# SPDX-License-Identifier: Apache-2.0
"""Qt custom source/proxy policy over complete scalar rows, never host handles."""

from typing import Any

from fontlabapp.glyphs.names.ui import QtGui
from fontlabapp.qt.tables.filter.model import Query, Row, sort_key


class CustomFilterModel(QtGui.QSortFilterProxyModel):
    """Keep the part2 Python matcher and comparator, with safe terminal callbacks."""

    def __init__(self, parent: Any) -> None:
        QtGui.QSortFilterProxyModel.__init__(self, parent)
        self._rows: tuple[Row, ...] = ()
        self._query = Query()
        self._active = True
        self.error = ""

    def configure(self, rows: tuple[Row, ...], query: Query) -> None:
        self._rows, self._query, self.error, self._active = rows, query, "", True
        self.invalidate()

    def deactivate(self) -> None:
        """Release all snapshot/query state before model or widget destruction."""
        self._active, self._rows, self._query = False, (), None

    def filterAcceptsRow(self, row: int, parent: Any) -> bool:
        if not self._active:
            return False
        try:
            return self._query.accepts(self._rows[row])
        except Exception as error:  # noqa: BLE001 - exceptions cannot escape a native virtual
            self.error = str(error)
            return False

    def lessThan(self, left: Any, right: Any) -> bool:
        if not self._active:
            return False
        try:
            column = left.column()
            a, b = self._rows[left.row()][column], self._rows[right.row()][column]
            return sort_key(a, column, self._query.sort_sensitive) < sort_key(
                b, column, self._query.sort_sensitive
            )
        except Exception as error:  # noqa: BLE001 - exceptions cannot escape a native virtual
            self.error = str(error)
            return False
