# this_file: src/fontlabapp/qt/tables/filter/official.py
# SPDX-License-Identifier: Apache-2.0
"""Typed Qt date cells and complete part3 controller policy for the shared UI."""

from typing import Any

from fontlabapp.qt.tables.filter.controls import value
from fontlabapp.glyphs.names.ui import QtCore, QtGui
from fontlabapp.qt.tables.filter.official_proxy import DateRangeProxy, LocaleDateProxy


def proxy(parent: Any, custom: bool) -> Any:
    return (DateRangeProxy if custom else LocaleDateProxy)(parent)


def item(column: int, text: str, epoch: int | None = None) -> Any:
    if column != 2:
        return QtGui.QStandardItem(text)
    stamp = (
        QtCore.QDateTime.fromMSecsSinceEpoch(epoch)
        if epoch is not None
        else QtCore.QDateTime.fromString(text, "yyyy-MM-dd HH:mm:ss")
    )
    if text and not stamp.isValid():
        raise ValueError("A captured date cannot be represented as a Qt datetime.")
    result = QtGui.QStandardItem()
    result.setData(stamp, QtCore.Qt.DisplayRole)
    return result


def update(dialog: Any) -> None:
    """Preserve original Qt regexp modes and the distinct custom date policy."""
    pattern = str(value(dialog.pattern, "text"))
    sensitivity = (
        QtCore.Qt.CaseSensitive
        if dialog.filter_case.isChecked()
        else QtCore.Qt.CaseInsensitive
    )
    syntax = (
        QtCore.QRegExp.RegExp,
        QtCore.QRegExp.Wildcard,
        QtCore.QRegExp.FixedString,
    )[int(value(dialog.syntax, "currentIndex"))]
    model = dialog.proxy
    model.error = ""
    if dialog.custom:
        limited = dialog.limit_dates.isChecked()
        model.setFilterMinimumDate(
            value(dialog.date_from, "date") if limited else QtCore.QDate()
        )
        model.setFilterMaximumDate(
            value(dialog.date_to, "date") if limited else QtCore.QDate()
        )
    else:
        model.setFilterKeyColumn(int(value(dialog.column, "currentIndex")))
        model.setSortCaseSensitivity(
            QtCore.Qt.CaseSensitive
            if dialog.sort_case.isChecked()
            else QtCore.Qt.CaseInsensitive
        )
    model.setFilterRegExp(QtCore.QRegExp(pattern, sensitivity, syntax))
    model.invalidate()
    count = model.rowCount()
    if model.error:
        raise ValueError(model.error)
    dialog.status.setText(
        f"Showing {count} of {len(dialog.table_data.rows)} captured rows. Refresh after font changes."
    )
