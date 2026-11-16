# this_file: src/fontlabapp/qt/tables/filter/official_proxy.py
# SPDX-License-Identifier: Apache-2.0
"""Part3 Qt date/regexp policies; no FontLab or foreign-font model dependency."""

from typing import Any

from fontlabapp.qt.tables.filter.controls import value
from fontlabapp.glyphs.names.ui import QtCore, QtGui


def locale_text(stamp: Any) -> str:
    """Default-locale short datetime, equivalent to Qt5 DefaultLocaleShortDate."""
    return str(QtCore.QLocale().toString(stamp, QtCore.QLocale.ShortFormat))


class LocaleDateProxy(QtGui.QSortFilterProxyModel):
    """Keep native basic filtering except the original locale-date override."""

    def __init__(self, parent: Any) -> None:
        QtGui.QSortFilterProxyModel.__init__(self, parent)
        self._active = True
        self.error = ""

    def activate(self) -> None:
        self._active, self.error = True, ""

    def deactivate(self) -> None:
        self._active = False

    def filterAcceptsRow(self, row: int, parent: Any) -> bool:
        if not self._active:
            return False
        try:
            if int(value(self, "filterKeyColumn")) == 2:
                model = value(self, "sourceModel")
                stamp = model.data(model.index(row, 2, parent))
                return value(self, "filterRegExp").indexIn(locale_text(stamp)) >= 0
            return QtGui.QSortFilterProxyModel.filterAcceptsRow(self, row, parent)
        except Exception as error:  # noqa: BLE001 - never escape a native virtual
            self.error = str(error)
            return False


class DateRangeProxy(LocaleDateProxy):
    """Original native regexp OR, inclusive days and case-sensitive comparator."""

    def __init__(self, parent: Any) -> None:
        super().__init__(parent)
        self.minDate, self.maxDate = QtCore.QDate(), QtCore.QDate()

    def setFilterMinimumDate(self, date: Any) -> None:
        self.minDate = date
        self.invalidate()

    def filterMinimumDate(self) -> Any:
        return self.minDate

    def setFilterMaximumDate(self, date: Any) -> None:
        self.maxDate = date
        self.invalidate()

    def filterMaximumDate(self) -> Any:
        return self.maxDate

    def dateInRange(self, date: Any) -> bool:
        if isinstance(date, QtCore.QDateTime):
            date = value(date, "date")
        return (
            not self.minDate.isValid()
            or date.toJulianDay() >= self.minDate.toJulianDay()
        ) and (
            not self.maxDate.isValid()
            or date.toJulianDay() <= self.maxDate.toJulianDay()
        )

    def filterAcceptsRow(self, row: int, parent: Any) -> bool:
        if not self._active:
            return False
        try:
            model, pattern = value(self, "sourceModel"), value(self, "filterRegExp")
            first, second, date = (
                model.data(model.index(row, col, parent)) for col in range(3)
            )
            return (
                pattern.indexIn(first) >= 0 or pattern.indexIn(second) >= 0
            ) and self.dateInRange(date)
        except Exception as error:  # noqa: BLE001 - never escape a native virtual
            self.error = str(error)
            return False

    def lessThan(self, left: Any, right: Any) -> bool:
        if not self._active:
            return False
        try:
            model = value(self, "sourceModel")
            a, b = model.data(left), model.data(right)
            if isinstance(a, (QtCore.QDate, QtCore.QDateTime)):
                return a.toString(QtCore.Qt.ISODate) < b.toString(QtCore.Qt.ISODate)
            email = QtCore.QRegExp(r"([\w\.]*@[\w\.]*)")
            if left.column() == 1 and email.indexIn(a) != -1:
                a = email.cap(1)
            if right.column() == 1 and email.indexIn(b) != -1:
                b = email.cap(1)
            return str(a) < str(b)
        except Exception as error:  # noqa: BLE001 - never escape a native virtual
            self.error = str(error)
            return False
