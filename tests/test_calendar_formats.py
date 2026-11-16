# this_file: tests/test_calendar_formats.py
"""Exact calendar colours, page markers and host-safe date surface palettes."""

from types import SimpleNamespace as NS

import pytest
from fontlabapp.qt.calendars.classic.controls import value
from fontlabapp.qt.calendars.classic.formats import first_friday
from test_calendar_controls import QtCore, QtGui
from test_calendar_controls import (
    controls as controls,  # noqa: PLC0414 - explicit pytest fixture re-export
)


@pytest.mark.parametrize(
    "group, colours",
    [
        ("weekday", ["black", "blue", "green"]),
        ("weekend", ["red", "blue", "black"]),
        ("header", ["black", "green", "blue"]),
    ],
)
@pytest.mark.parametrize("index", [0, 1, 2])
def test_calendar_when_colour_changes_then_exact_native_formats(
    controls, group, colours, index
):
    controls.combos[group].setCurrentIndex(index)
    cal = controls.calendar
    if group == "header":
        actual = cal.headerTextFormat()
    else:
        actual = cal.weekdayTextFormat(
            QtCore.Qt.Monday if group == "weekday" else QtCore.Qt.Sunday
        )
    assert actual.foreground().color().name() == QtGui.QColor(colours[index]).name()


@pytest.mark.parametrize(
    "year, month", [(2026, m) for m in range(1, 13)] + [(2027, 1), (2024, 2)]
)
def test_calendar_when_special_and_page_change_then_old_marks_clear(
    controls, year, month
):
    c = controls
    c.calendar.setCurrentPage(2025, 8)
    c.checks["special"].setChecked(True)
    old = QtCore.QDate(2025, 8, first_friday(2025, 8))
    c.calendar.setCurrentPage(year, month)
    marked = QtCore.QDate(year, month, first_friday(year, month))
    assert c.calendar.dateTextFormat(marked).background().color().name() == "#e6cb7a"
    assert (
        c.calendar.dateTextFormat(QtCore.QDate(year, 1, 1)).background().color().name()
        == "#e6cb7a"
    )
    assert c.calendar.dateTextFormat(old).background().style() == QtCore.Qt.NoBrush
    c.checks["special"].setChecked(False)
    assert c.calendar.dateTextFormat(marked).background().style() == QtCore.Qt.NoBrush


@pytest.mark.parametrize("choice", [-1, 3, None, True])
def test_calendar_formats_when_invalid_colour_choice_then_refuse_before_native_calls(
    controls, choice
):
    from fontlabapp.qt.calendars.classic.formats import apply

    with pytest.raises(ValueError):
        apply(
            controls.qt,
            None,
            year=2026,
            month=3,
            weekday=choice,
            weekend=0,
            header=0,
            special=False,
        )


def test_calendar_format_reads_pythonqt_checked_property_shape(controls):
    controls.checks["special"] = NS(checked=True)
    controls._format()
    assert len(controls._marked) == 2


def test_calendar_named_colour_surface_stays_readable_without_changing_parent_theme(
    controls,
):
    parent = controls.widget.parentWidget()
    palette = QtGui.QPalette(parent.palette())
    palette.setColor(QtGui.QPalette.Window, QtGui.QColor("#22242a"))
    palette.setColor(QtGui.QPalette.Base, QtGui.QColor("#181a1f"))
    palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor("#252830"))
    parent.setPalette(palette)
    actual = value(controls.calendar, "palette")
    assert actual.color(QtGui.QPalette.Base).name() == "#ffffff", (
        "named black remains readable"
    )
    assert actual.color(QtGui.QPalette.WindowText).name() == "#000000"
    assert actual.color(QtGui.QPalette.AlternateBase).name() == "#f5f6f8"
    assert (
        actual.color(QtGui.QPalette.Disabled, QtGui.QPalette.Text).name() == "#6b7280"
    )
    assert parent.palette().color(QtGui.QPalette.Window).name() == "#22242a", (
        "preserve owner theme"
    )
    assert (
        controls.combos["locale"].palette().color(QtGui.QPalette.Window).name()
        == "#22242a"
    )


def test_calendar_surface_accepts_pythonqt_property_and_copies_palette(controls):
    from fontlabapp.qt.calendars.classic.formats import surface

    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.Base, QtGui.QColor("#777777"))
    surface(controls.qt, NS(palette=palette, setPalette=controls.calendar.setPalette))
    assert palette.color(QtGui.QPalette.Base).name() == "#777777", (
        "leave the input palette unchanged"
    )
    assert (
        value(controls.calendar, "palette").color(QtGui.QPalette.Base).name()
        == "#ffffff"
    )
