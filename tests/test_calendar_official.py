# this_file: tests/test_calendar_official.py
"""Complete distinct part3 locale/week/header/date-format workflow in owned Qt."""

import os
from types import SimpleNamespace as NS

import pytest
from fontlabapp.qt.calendars.classic.controls import value
from fontlabapp.qt.calendars.official.controls import Controls, locale_options

if os.environ.get("FONTLABAPP_TEST_QT5") == "1":
    from PyQt5 import QtCore, QtGui, QtWidgets
else:
    from PySide6 import QtCore, QtGui, QtWidgets
APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def official():
    parent = QtWidgets.QWidget()
    gui = NS(**{n: getattr(QtGui, n) for n in dir(QtGui) if n.startswith("Q")})
    gui.__dict__.update(
        {n: getattr(QtWidgets, n) for n in dir(QtWidgets) if n.startswith("Q")}
    )
    pairs = []

    def connect(signal, slot):
        signal.connect(slot)
        pairs.append((signal, slot))

    controls = Controls(NS(QtCore=QtCore, QtGui=gui), parent, connect)
    yield controls
    controls.close()
    for signal, slot in reversed(pairs):
        signal.disconnect(slot)
    parent.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_official_defaults_and_every_locale_entry_preserve_native_order_and_labels(
    official,
):
    c = official
    original = QtCore.QLocale.matchingLocales(
        QtCore.QLocale.AnyLanguage, QtCore.QLocale.AnyScript, QtCore.QLocale.AnyCountry
    )
    assert tuple(original) == c.locales and c.combos["locale"].count() == len(original)
    for index, locale in enumerate(original):
        country = (
            getattr(locale, "nativeTerritoryName", None) or locale.nativeCountryName
        )
        assert (
            c.combos["locale"].itemText(index)
            == locale.nativeLanguageName() + "/" + country()
        )
    assert c.calendar.isGridVisible() and c.calendar.isNavigationBarVisible()
    assert value(c.calendar, "minimumDate") == QtCore.QDate(1900, 1, 1)
    assert value(c.calendar, "maximumDate") == QtCore.QDate(3000, 1, 1)
    assert value(c.calendar, "firstDayOfWeek") == QtCore.Qt.Sunday
    assert c.combos["horizontal"].currentIndex() == 1
    assert (
        value(c.calendar, "horizontalHeaderFormat")
        == QtWidgets.QCalendarWidget.ShortDayNames
    )
    assert (
        value(c.calendar, "selectionMode") == QtWidgets.QCalendarWidget.SingleSelection
    )
    assert c.calendar.headerTextFormat().fontWeight() == int(QtGui.QFont.Bold)
    assert c.dates["selected"].displayFormat() == "MMM d yyyy"
    assert not c.checks["friday"].isChecked() and not c.checks["holiday"].isChecked()


@pytest.mark.parametrize("index", range(7))
def test_official_week_start_keeps_all_seven_original_values(official, index):
    official.combos["week"].setCurrentIndex(index)
    assert value(official.calendar, "firstDayOfWeek") == getattr(
        QtCore.Qt,
        ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")[
            index
        ],
    )


@pytest.mark.parametrize("position", [0, 0.5, 1])
def test_official_locale_selection_uses_the_corresponding_exact_value(
    official, position
):
    index = int((len(official.locales) - 1) * position)
    official.combos["week"].setCurrentIndex(5)
    official.combos["locale"].setCurrentIndex(index)
    assert value(official.calendar, "locale") == official.locales[index]
    assert value(official.calendar, "firstDayOfWeek") == QtCore.Qt.Friday


@pytest.mark.parametrize("index", range(3))
def test_official_header_styles_bold_italic_plain_are_exact(official, index):
    official.combos["header"].setCurrentIndex(index)
    fmt = official.calendar.headerTextFormat()
    assert fmt.fontWeight() == (
        int(QtGui.QFont.Bold) if index == 0 else int(QtGui.QFont.Normal)
    )
    assert fmt.fontItalic() is (index == 1)


@pytest.mark.parametrize("key,day", [("weekday", 1), ("weekend", 7)])
@pytest.mark.parametrize(
    "index,colour", list(enumerate(["red", "blue", "black", "magenta"]))
)
def test_official_all_colour_choices_apply_to_their_week_group(
    official, key, day, index, colour
):
    official.combos[key].setCurrentIndex(index)
    weekday = QtCore.Qt.Monday if day == 1 else QtCore.Qt.Sunday
    assert (
        official.calendar.weekdayTextFormat(weekday).foreground().color().name()
        == QtGui.QColor(colour).name()
    )


@pytest.mark.parametrize("friday", [False, True])
@pytest.mark.parametrize("holiday", [False, True])
def test_official_date_marks_are_independent_and_may_first_wins_collision(
    official, friday, holiday
):
    c = official
    c.calendar.setCurrentPage(2026, 5)
    c.checks["friday"].setChecked(friday)
    c.checks["holiday"].setChecked(holiday)
    fmt = c.calendar.dateTextFormat(QtCore.QDate(2026, 5, 1))
    if friday or holiday:
        assert fmt.foreground().color().name() == ("#ff0000" if holiday else "#0000ff")
    else:
        assert fmt.isEmpty()
    c.calendar.setCurrentPage(2026, 6)
    assert (
        c.calendar.dateTextFormat(QtCore.QDate(2026, 5, 1)).foreground().color().name()
        == "#ff0000"
        if holiday
        else c.calendar.dateTextFormat(QtCore.QDate(2026, 5, 1)).isEmpty()
    )
    assert (
        c.calendar.dateTextFormat(QtCore.QDate(2026, 6, 5)).foreground().color().name()
        == "#0000ff"
        if friday
        else c.calendar.dateTextFormat(QtCore.QDate(2026, 6, 5)).isEmpty()
    )
    c.checks["friday"].setChecked(False)
    c.checks["holiday"].setChecked(False)
    assert (
        c.calendar.dateTextFormat(QtCore.QDate(2026, 5, 1)).isEmpty()
        and c.calendar.dateTextFormat(QtCore.QDate(2026, 6, 5)).isEmpty()
    )


def test_official_date_limits_match_source_domain_and_crossing_values(official):
    c = official
    assert value(c.dates["minimum"], "minimumDate") == QtCore.QDate(1900, 1, 1)
    assert value(c.dates["maximum"], "maximumDate") == QtCore.QDate(3000, 1, 1)
    c.dates["minimum"].setDate(QtCore.QDate(2800, 1, 1))
    c.dates["maximum"].setDate(QtCore.QDate(2000, 1, 1))
    assert value(c.calendar, "selectedDate") == QtCore.QDate(2000, 1, 1)
    assert value(c.dates["selected"], "date") == QtCore.QDate(2000, 1, 1)


def test_official_close_fences_callbacks_and_releases_locale_values(official):
    c = official
    c.close()
    before = c.calendar.isGridVisible()
    c.checks["grid"].setChecked(not before)
    assert c._closed and c.locales == () and c.calendar.isGridVisible() is before


def test_official_locale_helper_preserves_duplicates_and_last_matching_native_label():
    class Locale:
        AnyLanguage = 1
        AnyScript = 2
        AnyCountry = 3

        def __init__(self, name):
            self.name = name

        def nativeLanguageName(self):
            return self.name

        def nativeCountryName(self):
            return "country"

        @staticmethod
        def matchingLocales(*args):
            assert args == (1, 2, 3)
            return [Locale("other"), Locale("current"), Locale("current")]

    locales, labels, current = locale_options(Locale, Locale("current"))
    assert (
        len(locales) == 3
        and labels == ("other/country", "current/country", "current/country")
        and current == 2
    )
    assert locale_options(Locale, Locale("absent"))[2] == 0
    Locale.matchingLocales = lambda *args: []
    with pytest.raises(ValueError, match="locale"):
        locale_options(Locale, Locale("current"))


@pytest.mark.parametrize(
    "index,expected",
    [
        (0, "SingleLetterDayNames"),
        (1, "ShortDayNames"),
        (2, "LongDayNames"),
        (3, "NoHorizontalHeader"),
    ],
)
def test_official_horizontal_modes_keep_their_distinct_source_order(
    official, index, expected
):
    official.combos["horizontal"].setCurrentIndex(index)
    assert value(official.calendar, "horizontalHeaderFormat") == getattr(
        QtWidgets.QCalendarWidget, expected
    )


@pytest.mark.parametrize(
    "key,index,method,expected",
    [
        ("selection", 1, "selectionMode", "NoSelection"),
        ("vertical", 1, "verticalHeaderFormat", "NoVerticalHeader"),
    ],
)
def test_official_other_native_modes_are_preserved(
    official, key, index, method, expected
):
    official.combos[key].setCurrentIndex(index)
    assert value(official.calendar, method) == getattr(
        QtWidgets.QCalendarWidget, expected
    )


@pytest.mark.parametrize(
    "key,getter", [("grid", "isGridVisible"), ("navigation", "isNavigationBarVisible")]
)
def test_official_display_flags_roundtrip(official, key, getter):
    official.checks[key].setChecked(False)
    assert not getattr(official.calendar, getter)()
    official.checks[key].setChecked(True)
    assert getattr(official.calendar, getter)()


@pytest.mark.parametrize("header", ["Green", "Plain", "Other"])
def test_official_latent_header_rule_preserves_original_programmatic_semantics(
    official, header
):
    from fontlabapp.qt.calendars.official.formats import apply

    apply(
        official.qt,
        official.calendar,
        year=2026,
        month=5,
        weekday=2,
        weekend=0,
        header=header,
        friday=False,
        holiday=False,
    )
    fmt = official.calendar.headerTextFormat()
    assert (
        fmt.foreground().color().name() == "#008000"
        if header == "Green"
        else fmt.isEmpty()
    )


@pytest.mark.parametrize("choice", [-1, 4, None, True])
def test_official_invalid_colour_refuses_before_any_calendar_call(official, choice):
    from fontlabapp.qt.calendars.official.formats import apply

    with pytest.raises(ValueError):
        apply(
            official.qt,
            None,
            year=2026,
            month=5,
            weekday=choice,
            weekend=0,
            header="Bold",
            friday=False,
            holiday=False,
        )


def test_official_public_entry_refuses_worker_threads():
    from concurrent.futures import ThreadPoolExecutor

    from fontlabapp.glyphs.calendar.model import show_official

    with (
        ThreadPoolExecutor(max_workers=1) as pool,
        pytest.raises(RuntimeError, match="main UI thread"),
    ):
        pool.submit(show_official).result()


def test_official_public_entry_keeps_its_own_registry_and_complete_panel_policy(
    monkeypatch,
):
    import sys
    from types import ModuleType

    import fontlabapp.glyphs.catalog.native as native
    import fontlabapp.core.scripting as scripting_api
    from fontlabapp.glyphs.calendar.model import show_official

    module = ModuleType("fontlabapp.glyphs.calendar.ui")
    module.GlyphCalendarDialog = lambda parent, capture, **kw: (parent, capture, kw)
    monkeypatch.setitem(sys.modules, module.__name__, module)
    monkeypatch.setattr(
        scripting_api,
        "show_script_dialog",
        lambda factory, key: (factory("owned"), key),
    )
    assert show_official() == (
        ("owned", native.capture, {"official": True}),
        "glyph_modification_calendar_official",
    )
