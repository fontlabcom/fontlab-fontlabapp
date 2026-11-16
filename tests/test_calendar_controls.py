# this_file: tests/test_calendar_controls.py
"""Real owned standalone Qt calendar controls preserve all part2 options."""

import os
from types import SimpleNamespace as NS

import pytest
from fontlabapp.qt.calendars.classic.controls import Controls, value

if os.environ.get("FONTLABAPP_TEST_QT5") == "1":
    from PyQt5 import QtCore, QtGui, QtWidgets
else:
    from PySide6 import QtCore, QtGui, QtWidgets
APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def controls():
    parent = QtWidgets.QWidget()
    connections = []
    gui = NS(
        **{name: getattr(QtGui, name) for name in dir(QtGui) if name.startswith("Q")}
    )
    gui.__dict__.update(
        {
            name: getattr(QtWidgets, name)
            for name in dir(QtWidgets)
            if name.startswith("Q")
        }
    )

    def connect(signal, slot):
        signal.connect(slot)
        connections.append((signal, slot))

    controls = Controls(NS(QtCore=QtCore, QtGui=gui), parent, connect)
    yield controls
    controls.close()
    for signal, slot in reversed(connections):
        signal.disconnect(slot)
    parent.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_calendar_initial_controls_agree_with_rendered_defaults(controls):
    c, cal = controls, controls.calendar
    assert value(cal, "locale").name() == "en_US"
    assert value(cal, "firstDayOfWeek") == QtCore.Qt.Monday
    assert value(cal, "selectedDate") == value(c.dates["selected"], "date")
    assert value(cal, "minimumDate") == QtCore.QDate(1900, 1, 1)
    assert value(cal, "maximumDate") == QtCore.QDate(2100, 12, 31)
    assert not cal.isGridVisible() and cal.isNavigationBarVisible()
    assert (
        value(cal, "horizontalHeaderFormat") == QtWidgets.QCalendarWidget.ShortDayNames
    )
    assert (
        value(cal, "verticalHeaderFormat") == QtWidgets.QCalendarWidget.ISOWeekNumbers
    )
    assert value(cal, "selectionMode") == QtWidgets.QCalendarWidget.SingleSelection


@pytest.mark.parametrize("locale", ["en_US", "pl_PL", "de_DE"])
def test_calendar_when_locale_changes_then_selected_week_start_is_retained(
    controls, locale
):
    controls.combos["week"].setCurrentIndex(1)
    controls.combos["locale"].setCurrentIndex(["en_US", "pl_PL", "de_DE"].index(locale))
    assert value(controls.calendar, "locale").name() == locale
    assert value(controls.calendar, "firstDayOfWeek") == QtCore.Qt.Sunday


@pytest.mark.parametrize(
    "key, index, attribute, expected",
    [
        ("selection", 1, "selectionMode", "NoSelection"),
        ("selection", 0, "selectionMode", "SingleSelection"),
        ("horizontal", 0, "horizontalHeaderFormat", "ShortDayNames"),
        ("horizontal", 1, "horizontalHeaderFormat", "LongDayNames"),
        ("horizontal", 2, "horizontalHeaderFormat", "SingleLetterDayNames"),
        ("horizontal", 3, "horizontalHeaderFormat", "NoHorizontalHeader"),
        ("vertical", 0, "verticalHeaderFormat", "ISOWeekNumbers"),
        ("vertical", 1, "verticalHeaderFormat", "NoVerticalHeader"),
    ],
)
def test_calendar_when_option_changes_then_native_enum_matches(
    controls, key, index, attribute, expected
):
    controls.combos[key].setCurrentIndex(index)
    assert value(controls.calendar, attribute) == getattr(
        QtWidgets.QCalendarWidget, expected
    )


@pytest.mark.parametrize(
    "key, getter", [("grid", "isGridVisible"), ("navigation", "isNavigationBarVisible")]
)
@pytest.mark.parametrize("checked", [False, True])
def test_calendar_when_check_changes_then_native_flag_matches(
    controls, key, getter, checked
):
    controls.checks[key].setChecked(checked)
    assert getattr(controls.calendar, getter)() is checked


def test_calendar_when_dates_cross_then_all_editors_and_selection_stay_coherent(
    controls,
):
    c = controls
    c.dates["selected"].setDate(QtCore.QDate(2026, 3, 20))
    assert value(c.calendar, "selectedDate") == QtCore.QDate(2026, 3, 20)
    c.calendar.setSelectedDate(QtCore.QDate(2026, 4, 1))
    assert value(c.dates["selected"], "date") == QtCore.QDate(2026, 4, 1)
    for key, day in [
        ("minimum", QtCore.QDate(2200, 1, 1)),
        ("maximum", QtCore.QDate(1800, 1, 1)),
    ]:
        c.dates[key].setDate(day)
        assert value(c.calendar, "selectedDate") == day
        assert value(c.dates["selected"], "date") == day
        assert value(c.dates["minimum"], "date") == value(c.calendar, "minimumDate")
        assert value(c.dates["maximum"], "date") == value(c.calendar, "maximumDate")


def test_calendar_when_closed_then_late_callbacks_are_inert(controls):
    controls.close()
    before = controls.calendar.isGridVisible()
    controls.checks["grid"].setChecked(not before)
    assert controls.calendar.isGridVisible() is before
    controls.close()


def test_calendar_property_reader_supports_pythonqt_values_and_bound_methods():
    assert value(NS(a=3, b=lambda: 4), "a") == 3
    assert value(NS(a=3, b=lambda: 4), "b") == 4


def test_calendar_constructor_failure_fences_queued_slots_and_deletes_only_owned_widget():
    parent = QtWidgets.QWidget()
    gui = NS(
        **{name: getattr(QtGui, name) for name in dir(QtGui) if name.startswith("Q")}
    )
    gui.__dict__.update(
        {
            name: getattr(QtWidgets, name)
            for name in dir(QtWidgets)
            if name.startswith("Q")
        }
    )
    seen = []

    def fail(signal, slot):
        seen.append(slot)
        raise RuntimeError("owned connection failed")

    with pytest.raises(RuntimeError, match="owned connection failed"):
        Controls(NS(QtCore=QtCore, QtGui=gui), parent, fail)
    owner = next(
        cell.cell_contents
        for cell in seen[0].__closure__
        if isinstance(cell.cell_contents, Controls)
    )
    assert owner._closed and owner._connect is None
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    seen[0](1)
    assert parent.children() == [], (
        "the caller parent survives and the owned widget is deleted"
    )
    parent.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
