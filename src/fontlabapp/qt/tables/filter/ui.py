# this_file: src/fontlabapp/qt/tables/filter/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Owned modeless complete source/proxy filtering, independent of font APIs."""

import sys
from collections.abc import Callable
from time import monotonic
from typing import Any

from fontlabapp.qt.tables.filter.controls import build, populate, value
from fontlabapp.qt.tables.filter.proxy import CustomFilterModel
from fontlabapp.glyphs.names.ui import NamesDialog, QtCore, QtGui
from fontlabapp.qt.tables.filter.model import Query, Table


class FilterTableDialog(NamesDialog):
    """Own two read-only views, one complete model and every callback lifetime."""

    def __init__(
        self,
        parent: Any,
        title: str,
        key: str,
        capture: Callable[[], Table],
        custom: bool,
        description: str,
        *,
        official: bool = False,
    ) -> None:
        super().__init__(parent, title, key)
        self.KEY, self._capture, self.custom = key, capture, custom
        self.official = official
        self._closed, self._updating, self._dates_initialized = False, True, False
        self._disconnect_errors = []
        self.table_data = None
        build(self, custom, official)
        self.subtitle.setText(description)
        self.model = QtGui.QStandardItemModel(0, 3, self)
        if official:
            from fontlabapp.qt.tables.filter.official import proxy

            self.proxy = proxy(self, custom)
        else:
            self.proxy = (CustomFilterModel if custom else QtGui.QSortFilterProxyModel)(
                self
            )
        self.proxy.setDynamicSortFilter(True)
        self._completion_lifetime.on_destroyed.append(self._dispose)
        if parent is not None:
            self._connect(parent.destroyed, lambda *args: self._dispose())
        self._updating = False
        self.refresh()
        if not self._closed:
            hint = value(self.root, "sizeHint")
            height = int(value(hint, "height"))
            for view in (self.source_view, self.proxy_view):
                rows = min(8, self.model.rowCount())
                row_height = sum(view.sizeHintForRow(row) for row in range(rows))
                if not rows:
                    row_height = int(value(value(view, "fontMetrics"), "height")) + 2
                header_hint = value(value(view, "header"), "sizeHint")
                height += (
                    row_height + int(value(header_hint, "height")) + 2 * view.frameWidth()
                    - int(value(value(view, "sizeHint"), "height"))
                )
            self.resize(max(640, int(value(hint, "width"))), max(460, height))

    def _detach(self) -> None:
        if self.custom or self.official:
            self.proxy.deactivate()
        self.proxy_view.setModel(None)
        self.source_view.setModel(None)
        self.proxy.setSourceModel(None)
        self.model.clear()
        self.table_data = None

    def _fill(self, table: Table) -> None:
        populate(self, table, monotonic)
        selected = max(0, int(value(self.column, "currentIndex")))
        self.column.clear()
        self.column.addItems(list(table.headers))
        self.column.setCurrentIndex(selected)
        if self.custom and not self._dates_initialized:
            days = sorted(row[2][:10] for row in table.rows if row[2])
            if days:
                self.date_from.setDate(QtCore.QDate.fromString(days[0], "yyyy-MM-dd"))
                self.date_to.setDate(QtCore.QDate.fromString(days[-1], "yyyy-MM-dd"))
                self._dates_initialized = True
        self.table_data = table
        self.source_view.setModel(self.model)
        if self.official:
            self.proxy.activate()
            self.proxy.setFilterRegExp(QtCore.QRegExp())
        elif self.custom:
            self.proxy.configure(table.rows, Query())
        self.proxy.setSourceModel(self.model)
        self.proxy_view.setModel(self.proxy)
        for view in (self.source_view, self.proxy_view):
            header = value(view, "header")
            header.setStretchLastSection(False)
            header.setSectionResizeMode(QtGui.QHeaderView.ResizeToContents)
            header.setSectionResizeMode(1, QtGui.QHeaderView.Stretch)

    def refresh(self) -> None:
        """Install complete scalar rows or remove both views; keep user filters."""
        if self._closed:
            return
        self._updating = True
        try:
            self._detach()
            table = self._capture()
            if self._closed:
                return
            if not isinstance(table, Table):
                raise TypeError("Capture must return a complete immutable Table.")
            self._fill(table)
        except Exception as error:  # noqa: BLE001 - contain capture/native UI failures
            if not self._closed:
                self._detach()
                self.status.setText(str(error))
        finally:
            self._updating = False
        self.update_filter()

    def _query(self) -> Query:
        limited = self.custom and bool(self.limit_dates.isChecked())
        return Query(
            str(value(self.pattern, "text")),
            ("regular", "wildcard", "fixed")[int(value(self.syntax, "currentIndex"))],
            bool(self.filter_case.isChecked()),
            bool(self.sort_case.isChecked()),
            str(value(self.date_from, "date").toString("yyyy-MM-dd")) if limited else None,
            str(value(self.date_to, "date").toString("yyyy-MM-dd")) if limited else None,
        )

    def update_filter(self) -> None:
        if self._closed or self._updating or self.table_data is None:
            return
        try:
            if self.official:
                from fontlabapp.qt.tables.filter.official import update

                update(self)
                return
            query = self._query()
            sensitive = (
                QtCore.Qt.CaseSensitive
                if query.case_sensitive
                else QtCore.Qt.CaseInsensitive
            )
            self.proxy.setFilterCaseSensitivity(sensitive)
            self.proxy.setSortCaseSensitivity(
                QtCore.Qt.CaseSensitive
                if query.sort_sensitive
                else QtCore.Qt.CaseInsensitive
            )
            if self.custom:
                self.proxy.configure(self.table_data.rows, query)
                if self.proxy.error:
                    raise ValueError(self.proxy.error)
            else:
                self.proxy.setFilterKeyColumn(int(value(self.column, "currentIndex")))
                if query.syntax == "regular":
                    self.proxy.setFilterRegExp(QtCore.QRegExp(query.pattern, sensitive))
                elif query.syntax == "wildcard":
                    self.proxy.setFilterWildcard(query.pattern)
                else:
                    self.proxy.setFilterFixedString(query.pattern)
            self.status.setText(
                f"Showing {self.proxy.rowCount()} of {len(self.table_data.rows)} captured rows. Refresh after font changes."
            )
        except Exception as error:  # noqa: BLE001 - contain Qt signal/virtual failures
            self._detach()
            self.status.setText(str(error))

    def _dispose(self) -> None:
        """Release models and bound callbacks before children are destroyed."""
        if self._closed:
            return
        self._closed, self._capture = True, None
        try:
            self._detach()
        except Exception as error:  # noqa: BLE001 - teardown may follow native destruction
            self.table_data = None
            self._disconnect_errors.append(str(error))
        for signal, slot in reversed(tuple(self._connections)):
            try:
                signal.disconnect(slot)
            except Exception as error:  # noqa: BLE001 - attempt every connection
                self._disconnect_errors.append(str(error))
        self._connections.clear()
        windows = getattr(sys, "_fontlab_samples", {})
        if windows.get(self.KEY) is self:
            windows.pop(self.KEY)

    def closeEvent(self, event: Any) -> None:
        self._dispose()
        super().closeEvent(event)
