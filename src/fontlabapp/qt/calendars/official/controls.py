# this_file: src/fontlabapp/qt/calendars/official/controls.py
# SPDX-License-Identifier: Apache-2.0
"""Complete distinct part3 calendar policy over the shared injected Qt controls."""

from collections.abc import Callable
from typing import Any

from fontlabapp.qt.calendars.base import CalendarBase, value
from fontlabapp.qt.calendars.official.formats import apply


def _label(locale: Any) -> str:
    country = getattr(locale, "nativeTerritoryName", None) or locale.nativeCountryName
    return str(locale.nativeLanguageName()) + "/" + str(country())


def locale_options(
    locale_class: Any, current: Any
) -> tuple[tuple[Any, ...], tuple[str, ...], int]:
    """Keep all Qt locales in order, duplicates and the last matching native label."""
    locales = tuple(
        locale_class.matchingLocales(
            locale_class.AnyLanguage, locale_class.AnyScript, locale_class.AnyCountry
        )
    )
    if not locales:
        raise ValueError("Qt returned no calendar locales.")
    labels = tuple(_label(item) for item in locales)
    selected = 0
    current_label = _label(current)
    for index, label in enumerate(labels):
        if label == current_label:
            selected = index
    return locales, labels, selected


class Controls(CalendarBase):
    """Retain every part3 control with its separate source ranges and formatting."""

    def __init__(self, qt: Any, parent: Any, connect: Callable[..., None]) -> None:
        self.locales = ()
        super().__init__(qt, parent, connect, maximum=(3000, 1, 1))
        gui = qt.QtGui
        cal = self.calendar
        kind = gui.QCalendarWidget
        try:
            self.locales, labels, current = locale_options(
                qt.QtCore.QLocale, value(cal, "locale")
            )
            self._combo("locale", "Locale", labels, self._locale)
            combo = self.combos["locale"]
            combo.setMinimumContentsLength(20)
            combo.setSizeAdjustPolicy(
                gui.QComboBox.AdjustToMinimumContentsLengthWithIcon
            )
            combo.setMaxVisibleItems(20)
            self._combo(
                "week",
                "Week starts",
                (
                    "Sunday",
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday",
                    "Saturday",
                ),
                self._week,
            )
            self._combo(
                "selection",
                "Selection",
                ("Single date", "None"),
                lambda i: cal.setSelectionMode(
                    (kind.SingleSelection, kind.NoSelection)[i]
                ),
            )
            cal.setGridVisible(True)
            self._check("grid", "Grid", True, cal.setGridVisible)
            self._check("navigation", "Navigation", True, cal.setNavigationBarVisible)
            self._combo(
                "horizontal",
                "Day headings",
                ("Single letters", "Short names", "Long names", "None"),
                lambda i: cal.setHorizontalHeaderFormat(
                    (
                        kind.SingleLetterDayNames,
                        kind.ShortDayNames,
                        kind.LongDayNames,
                        kind.NoHorizontalHeader,
                    )[i]
                ),
            )
            self._combo(
                "vertical",
                "Week headings",
                ("Week numbers", "None"),
                lambda i: cal.setVerticalHeaderFormat(
                    (kind.ISOWeekNumbers, kind.NoVerticalHeader)[i]
                ),
            )
            self._make_dates(display_format="MMM d yyyy", source_limits=True)
            colours = ("Red", "Blue", "Black", "Magenta")
            self._combo("weekday", "Weekday colour", colours, self._format)
            self._combo("weekend", "Weekend colour", colours, self._format)
            self._combo(
                "header", "Header text", ("Bold", "Italic", "Plain"), self._format
            )
            self._check("friday", "First Friday in blue", False, self._format)
            self._check("holiday", "May 1 in red", False, self._format)
            self._link(cal.selectionChanged, self._sync_dates)
            self._link(cal.currentPageChanged, self._format)
            self.combos["weekday"].setCurrentIndex(2)
            self.combos["horizontal"].setCurrentIndex(1)
            self.combos["locale"].setCurrentIndex(current)
            self._locale(current)
            self._sync_dates()
            self._format()
        except BaseException:
            self._abort()
            raise

    def _locale(self, index: int) -> None:
        self.calendar.setLocale(self.locales[index])
        self.combos["locale"].setToolTip(_label(self.locales[index]))
        self._week(int(value(self.combos["week"], "currentIndex")))

    def _week(self, index: int) -> None:
        self.calendar.setFirstDayOfWeek(
            getattr(
                self.qt.QtCore.Qt,
                (
                    "Sunday",
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday",
                    "Saturday",
                )[index],
            )
        )

    def _format(self, *args: Any) -> None:
        self._marked = apply(
            self.qt,
            self.calendar,
            year=int(value(self.calendar, "yearShown")),
            month=int(value(self.calendar, "monthShown")),
            weekday=int(value(self.combos["weekday"], "currentIndex")),
            weekend=int(value(self.combos["weekend"], "currentIndex")),
            header=str(value(self.combos["header"], "currentText")),
            friday=bool(value(self.checks["friday"], "isChecked")),
            holiday=bool(value(self.checks["holiday"], "isChecked")),
            previous=self._marked,
        )

    def close(self) -> None:
        super().close()
        self.locales = ()
