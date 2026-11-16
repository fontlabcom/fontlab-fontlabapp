# this_file: src/fontlabapp/qt/calendars/classic/controls.py
# SPDX-License-Identifier: Apache-2.0
"""Complete part2 calendar policy over shared caller-owned Qt mechanics."""

from collections.abc import Callable
from typing import Any

import fontlabapp.qt.calendars.classic.formats as formats
from fontlabapp.qt.calendars.base import CalendarBase, value as value


class Controls(CalendarBase):
    """Retain every part2 option, its ordering/defaults and owned date markers."""

    def __init__(self, qt: Any, parent: Any, connect: Callable[..., None]) -> None:
        super().__init__(qt, parent, connect)
        gui = qt.QtGui
        try:
            cal = self.calendar
            self._combo("locale", "Locale", ("en_US", "pl_PL", "de_DE"), self._locale)
            self._combo("week", "Week starts", ("Monday", "Sunday"), self._week)
            self._combo(
                "selection",
                "Selection",
                ("Single date", "None"),
                lambda i: cal.setSelectionMode(
                    (
                        gui.QCalendarWidget.SingleSelection,
                        gui.QCalendarWidget.NoSelection,
                    )[i]
                ),
            )
            self._check("grid", "Grid", False, cal.setGridVisible)
            self._check("navigation", "Navigation", True, cal.setNavigationBarVisible)
            self._combo(
                "horizontal",
                "Day headings",
                ("Short names", "Long names", "Single letters", "None"),
                lambda i: cal.setHorizontalHeaderFormat(
                    (
                        gui.QCalendarWidget.ShortDayNames,
                        gui.QCalendarWidget.LongDayNames,
                        gui.QCalendarWidget.SingleLetterDayNames,
                        gui.QCalendarWidget.NoHorizontalHeader,
                    )[i]
                ),
            )
            self._combo(
                "vertical",
                "Week headings",
                ("Week numbers", "None"),
                lambda i: cal.setVerticalHeaderFormat(
                    (
                        gui.QCalendarWidget.ISOWeekNumbers,
                        gui.QCalendarWidget.NoVerticalHeader,
                    )[i]
                ),
            )
            self._make_dates()
            self._combo(
                "weekday", "Weekday colour", ("Black", "Blue", "Green"), self._format
            )
            self._combo(
                "weekend", "Weekend colour", ("Red", "Blue", "Black"), self._format
            )
            self._combo(
                "header", "Header colour", ("Black", "Green", "Blue"), self._format
            )
            self._check(
                "special", "First Friday and annual holiday", False, self._format
            )
            self._link(cal.selectionChanged, self._sync_dates)
            self._link(cal.currentPageChanged, self._format)
            self._locale(0)
            self._sync_dates()
            self._format()
        except BaseException:
            self._abort()
            raise

    def _locale(self, index: int) -> None:
        self.calendar.setLocale(
            self.qt.QtCore.QLocale(("en_US", "pl_PL", "de_DE")[index])
        )
        self._week(int(value(self.combos["week"], "currentIndex")))

    def _week(self, index: int) -> None:
        self.calendar.setFirstDayOfWeek(
            (self.qt.QtCore.Qt.Monday, self.qt.QtCore.Qt.Sunday)[index]
        )

    def _format(self, *args: Any) -> None:
        self._marked = formats.apply(
            self.qt,
            self.calendar,
            year=int(value(self.calendar, "yearShown")),
            month=int(value(self.calendar, "monthShown")),
            weekday=int(value(self.combos["weekday"], "currentIndex")),
            weekend=int(value(self.combos["weekend"], "currentIndex")),
            header=int(value(self.combos["header"], "currentIndex")),
            special=bool(
                value(self.checks["special"], "checked")
                if hasattr(self.checks["special"], "checked")
                else value(self.checks["special"], "isChecked")
            ),
            previous=self._marked,
        )
