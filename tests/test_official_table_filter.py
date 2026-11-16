# this_file: tests/test_official_table_filter.py
"""Whole part3 typed-date workflows, separately exercised in real Qt5 and Qt6."""

import sys
from types import SimpleNamespace as NS

import pytest
import test_filter_table_dialog as ui
from fontlabapp.qt.tables.filter.model import Table

panel = ui.panel


@pytest.fixture
def official(panel):
    base, state, custom = panel
    w = base.__class__(
        None,
        "Owned typed dates",
        "owned_typed_dates",
        lambda: Table(
            ("Glyph", "Unicode", "Modified"),
            state.rows,
            epochs=getattr(state, "epochs", None),
        ),
        custom,
        "Typed captured rows",
        official=True,
    )
    yield w, state, custom
    if ui.valid(w):
        w.close()
    ui.QtCore.QCoreApplication.sendPostedEvents(None, ui.QtCore.QEvent.DeferredDelete)


def test_typed_dates_when_built_then_source_types_defaults_and_chronological_sort(
    official,
):
    w, _, custom = official
    value = w.model.data(w.model.index(0, 2))
    assert isinstance(value, ui.QtCore.QDateTime) and value.isValid()
    assert w.filter_case.isChecked()
    assert w.column.currentIndex() == 1
    assert w.sort_case.isHidden() is custom
    assert w.column.isHidden() is custom
    assert (
        w.proxy.sortColumn() == 1 and w.proxy.sortOrder() == ui.QtCore.Qt.AscendingOrder
    )
    w.proxy.sort(2, ui.QtCore.Qt.AscendingOrder)
    assert ui.names(w) == ["a.alt", "B", "ß"]
    w.proxy.sort(2, ui.QtCore.Qt.DescendingOrder)
    assert ui.names(w) == ["ß", "B", "a.alt"]


@pytest.mark.parametrize("locale", ["en_US", "de_DE", "pl_PL"])
def test_basic_when_date_filter_selected_then_matches_locale_short_text_exactly(
    official, locale
):
    w, _, custom = official
    if custom:
        return
    before = ui.QtCore.QLocale()
    try:
        ui.QtCore.QLocale.setDefault(ui.QtCore.QLocale(locale))
        stamp = w.model.data(w.model.index(1, 2))
        text = ui.QtCore.QLocale().toString(stamp, ui.QtCore.QLocale.ShortFormat)
        if hasattr(ui.QtCore.Qt, "DefaultLocaleShortDate"):
            assert text == stamp.toString(ui.QtCore.Qt.DefaultLocaleShortDate)
        w.column.setCurrentIndex(2)
        w.syntax.setCurrentIndex(2)
        w.pattern.setText(text)
        assert ui.names(w) == ["B"]
        w.pattern.setText("2026-06-01 12:30:00")
        assert not ui.names(w), (
            "Date matching must use locale display text, not ISO source strings"
        )
    finally:
        ui.QtCore.QLocale.setDefault(before)


def test_custom_when_native_regex_and_ranges_then_distinct_from_part2_casefold(
    official,
):
    w, _, custom = official
    if not custom:
        return
    w.filter_case.setChecked(False)
    w.syntax.setCurrentIndex(2)
    w.pattern.setText("SS")
    assert not ui.names(w), "Official Custom uses Qt matching, not Python casefold"
    w.pattern.setText("")
    w.limit_dates.setChecked(True)
    w.date_from.setDate(ui.QtCore.QDate(2026, 6, 1))
    w.date_to.setDate(ui.QtCore.QDate(2026, 6, 1))
    assert ui.names(w) == ["B"]
    assert w.proxy.filterMinimumDate() == ui.QtCore.QDate(2026, 6, 1)
    assert w.proxy.filterMaximumDate() == ui.QtCore.QDate(2026, 6, 1)
    w.date_from.setDate(ui.QtCore.QDate(2026, 7, 1))
    assert not ui.names(w)
    w.limit_dates.setChecked(False)
    assert len(ui.names(w)) == 3


def test_custom_comparator_when_email_tokens_then_original_case_sensitive_extraction(
    official,
):
    w, state, custom = official
    if not custom:
        return
    state.rows = (
        ("first", "Writer <z@sample.invalid>", "2026-01-01 01:00:00"),
        ("second", "other <A@sample.invalid>", "2026-01-01 02:00:00"),
        ("third", "a+local@sample.invalid", "2026-01-01 03:00:00"),
    )
    # Refresh uses the same complete Table source, independent of the actual font adapter.
    w.refresh()
    w.proxy.sort(1, ui.QtCore.Qt.AscendingOrder)
    assert ui.names(w) == ["second", "third", "first"]
    w.sort_case.setChecked(False)
    assert ui.names(w) == ["second", "third", "first"], (
        "Source custom comparator has no case-sort switch"
    )


@pytest.mark.parametrize(
    "route", ["close", "reject", "accept", "done", "escape", "destroy"]
)
def test_typed_panel_when_completed_then_all_models_signals_and_rows_release(
    official, route
):
    w, _, _ = official
    proxy = w.proxy
    sys.__dict__.setdefault("_fontlab_samples", {})[w.KEY] = w
    w.show()
    if route == "close":
        w.close_button.click()
    elif route == "reject":
        w.reject()
    elif route == "accept":
        w.accept()
    elif route == "done":
        w.done(0)
    elif route == "destroy":
        w.deleteLater()
    else:
        if ui.os.environ.get("FONTLABAPP_TEST_QT5") == "1":
            from PyQt5.QtTest import QTest
        else:
            from PySide6.QtTest import QTest
        QTest.keyClick(w, ui.QtCore.Qt.Key_Escape)
    ui.QtCore.QCoreApplication.sendPostedEvents(None, ui.QtCore.QEvent.DeferredDelete)
    assert w._closed and w._capture is None and not w._connections
    assert w.KEY not in sys._fontlab_samples
    assert proxy.filterAcceptsRow(0, ui.QtCore.QModelIndex()) is False


def test_typed_refresh_when_invalid_or_missing_date_then_no_prefix_and_explicit_qt_value(
    official,
):
    w, state, custom = official
    state.rows = (("bad", "", "not-a-date"),)
    w.refresh()
    assert (
        w.table_data is None
        and w.model.rowCount() == 0
        and "represented" in w.status.text()
    )
    state.rows = (("missing", "", ""),)
    w.refresh()
    assert isinstance(w.model.data(w.model.index(0, 2)), ui.QtCore.QDateTime)
    assert not w.model.data(w.model.index(0, 2)).isValid()
    assert ui.names(w) == ["missing"]
    if custom:
        w.limit_dates.setChecked(True)
        assert not ui.names(w)
        assert w.proxy.dateInRange(ui.QtCore.QDate(2026, 6, 1))


def test_virtual_errors_when_owned_model_callbacks_fail_then_contained_and_complete_view_clears(
    official, monkeypatch
):
    w, _, custom = official
    if custom:

        def broken(date):
            raise ValueError("owned date failure")

        monkeypatch.setattr(w.proxy, "dateInRange", broken)
    else:
        w.column.setCurrentIndex(2)
        module = sys.modules["fontlabapp.qt.tables.filter.official_proxy"]

        def broken(date):
            raise ValueError("owned date failure")

        monkeypatch.setattr(module, "locale_text", broken)
    w.update_filter()
    assert w.table_data is None and w.model.rowCount() == 0 and w.proxy.rowCount() == 0
    assert "owned date failure" in w.status.text()


def test_custom_comparator_when_bad_index_then_failure_contained_and_closed_callback_inert(
    official,
):
    w, _, custom = official
    if not custom:
        return
    bad = NS(column=lambda: 1, row=lambda: 100)
    assert w.proxy.lessThan(bad, bad) is False and w.proxy.error
    w.proxy.deactivate()
    assert w.proxy.lessThan(bad, bad) is False


def test_public_official_routes_when_called_then_same_complete_metadata_source_and_policy(
    monkeypatch,
):
    from unittest.mock import Mock

    import fontlabapp.glyphs.catalog.model as catalog
    import fontlabapp.qt.tables.filter.model as table

    shown = Mock(return_value="owned")
    monkeypatch.setattr(table, "show", shown)
    assert catalog.show_official_basic() == "owned"
    assert shown.call_args.kwargs["official"] and not shown.call_args.kwargs["custom"]
    assert catalog.show_official_custom() == "owned"
    assert shown.call_args.kwargs["official"] and shown.call_args.kwargs["custom"]
    assert shown.call_args.args[0].__module__ == "fontlabapp.glyphs.catalog.native"


def test_epoch_channel_when_same_display_second_then_typed_cells_preserve_exact_instants(
    official,
):
    w, state, custom = official
    instant = ui.QtCore.QDateTime.fromString(
        "2026-10-25T02:30:00+02:00", ui.QtCore.Qt.ISODate
    ).toMSecsSinceEpoch()
    state.rows = (
        ("late", "", "2026-10-25 02:30:00"),
        ("early", "", "2026-10-25 02:30:00"),
    )
    state.epochs = (instant + 101, instant + 100)
    w.refresh()
    assert [
        w.model.data(w.model.index(i, 2)).toMSecsSinceEpoch() for i in range(2)
    ] == list(state.epochs)
    w.proxy.sort(2, ui.QtCore.Qt.AscendingOrder)
    if not custom:
        assert ui.names(w) == ["early", "late"]
    else:
        left, right = w.model.index(0, 2), w.model.index(1, 2)
        assert not w.proxy.lessThan(left, right) and not w.proxy.lessThan(
            right, left
        ), "Keep the original custom ISODate comparator without milliseconds"
