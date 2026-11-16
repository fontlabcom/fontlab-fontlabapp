# this_file: src/fontlabapp/qt/calendars/classic/formats.py
# SPDX-License-Identifier: Apache-2.0
"""Apply the full part2 weekday/weekend/header and owned special-date formats.

Qt is injected. The special switch marks the displayed month's first Friday and
January 1 of that year. Clear only the dates previously marked by this helper.
This is intentionally separate from part3's bold/italic headers and May 1 rule.
"""

from datetime import date
from typing import Any


def first_friday(year: int, month: int) -> int:
    """Return the month's first Friday; invalid years/months refuse via date."""
    return 1 + (4 - date(year, month, 1).weekday()) % 7


def apply(
    qt: Any,
    calendar: Any,
    *,
    year: int,
    month: int,
    weekday: int,
    weekend: int,
    header: int,
    special: bool,
    previous: tuple[Any, ...] = (),
) -> tuple[Any, ...]:
    """Set all advertised formats; return the exact newly owned date markers."""
    if any(
        type(index) is not int or not 0 <= index < 3
        for index in (weekday, weekend, header)
    ):
        raise ValueError("Calendar colour choices require indices 0 through 2.")
    gui, core = qt.QtGui, qt.QtCore
    days = (
        core.Qt.Monday,
        core.Qt.Tuesday,
        core.Qt.Wednesday,
        core.Qt.Thursday,
        core.Qt.Friday,
        core.Qt.Saturday,
        core.Qt.Sunday,
    )
    for index, day in enumerate(days):
        colour = (
            ("black", "blue", "green")[weekday]
            if index < 5
            else ("red", "blue", "black")[weekend]
        )
        text = gui.QTextCharFormat()
        text.setForeground(gui.QBrush(gui.QColor(colour)))
        calendar.setWeekdayTextFormat(day, text)
    text = gui.QTextCharFormat()
    text.setForeground(gui.QBrush(gui.QColor(("black", "green", "blue")[header])))
    calendar.setHeaderTextFormat(text)
    for marked in previous:
        calendar.setDateTextFormat(marked, gui.QTextCharFormat())
    dates = ()
    if special:
        dates = (
            core.QDate(year, month, first_friday(year, month)),
            core.QDate(year, 1, 1),
        )
        for marked in dates:
            text = gui.QTextCharFormat()
            text.setBackground(gui.QBrush(gui.QColor("#e6cb7a")))
            calendar.setDateTextFormat(marked, text)
    return dates


def surface(qt: Any, calendar: Any) -> None:
    """Keep explicit named text colours readable on this owned date surface.

    The surrounding form/report retain their host palette. Copy this widget's
    palette before changing its date-surface roles; never change application
    or parent palettes, preferences, stylesheets or global theme settings.
    """
    item = calendar.palette
    palette = qt.QtGui.QPalette(item() if callable(item) else item)
    for role, colour in (
        (qt.QtGui.QPalette.Base, "white"),
        (qt.QtGui.QPalette.Window, "white"),
        (qt.QtGui.QPalette.AlternateBase, "#f5f6f8"),
        (qt.QtGui.QPalette.Text, "black"),
        (qt.QtGui.QPalette.WindowText, "black"),
    ):
        palette.setColor(role, qt.QtGui.QColor(colour))
    palette.setColor(
        qt.QtGui.QPalette.Disabled, qt.QtGui.QPalette.Text, qt.QtGui.QColor("#6b7280")
    )
    calendar.setPalette(palette)
