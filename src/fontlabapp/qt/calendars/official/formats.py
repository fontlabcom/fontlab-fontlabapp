# this_file: src/fontlabapp/qt/calendars/official/formats.py
# SPDX-License-Identifier: Apache-2.0
"""Keep part3 font-style headers, weekday colours and two independent date rules."""

from typing import Any

from fontlabapp.qt.calendars.classic.formats import first_friday


def apply(
    qt: Any,
    calendar: Any,
    *,
    year: int,
    month: int,
    weekday: int,
    weekend: int,
    header: str,
    friday: bool,
    holiday: bool,
    previous: tuple[Any, ...] = (),
) -> tuple[Any, ...]:
    """Replace only owned marks; May1 red wins when it is also the first Friday.

    The UI offers Bold/Italic/Plain. Keep the original latent Green header rule
    for programmatic callers without adding a new choice to that original UI.
    """
    if any(
        type(index) is not int or not 0 <= index < 4 for index in (weekday, weekend)
    ):
        raise ValueError("Official calendar colours require indices 0 through 3.")
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
        text = gui.QTextCharFormat()
        text.setForeground(
            gui.QBrush(
                gui.QColor(
                    ("red", "blue", "black", "magenta")[
                        weekday if index < 5 else weekend
                    ]
                )
            )
        )
        calendar.setWeekdayTextFormat(day, text)
    text = gui.QTextCharFormat()
    if header == "Bold":
        text.setFontWeight(int(gui.QFont.Bold))
    elif header == "Italic":
        text.setFontItalic(True)
    elif header == "Green":
        text.setForeground(gui.QBrush(gui.QColor("green")))
    calendar.setHeaderTextFormat(text)
    for marked in previous:
        calendar.setDateTextFormat(marked, gui.QTextCharFormat())
    marks = []
    if friday:
        marks.append((core.QDate(year, month, first_friday(year, month)), "blue"))
    if holiday:
        marks.append((core.QDate(year, 5, 1), "red"))
    for marked, colour in marks:
        text = gui.QTextCharFormat()
        text.setForeground(gui.QBrush(gui.QColor(colour)))
        calendar.setDateTextFormat(marked, text)
    return tuple(marked for marked, _ in marks)
