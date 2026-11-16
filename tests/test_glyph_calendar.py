# this_file: tests/test_glyph_calendar.py
"""Complete local calendar-day matching keeps glyph order and exact scalar data."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest
from fontlabapp.glyphs.calendar.model import on_day, show
from fontlabapp.qt.tables.filter.model import Table

ROWS = (
    ("A", "U+0041 U+0391", "2026-03-20 23:59:59"),
    ("a.alt", "", "2026-03-20 00:00:00"),
    ("B", "U+0042", "2026-03-21 00:00:00"),
    ("undated", "", ""),
)


def test_calendar_day_when_matches_then_order_codes_unencoded_and_epochs_survive():
    table = Table(("Name", "Unicode", "Modified"), ROWS, (1, 2, 3, None))
    result = on_day(table, "2026-03-20")
    assert result.rows == ROWS[:2] and result.epochs == (1, 2)
    assert result.headers == table.headers and table.rows == ROWS


@pytest.mark.parametrize("rows", [(), (("a", "", ""),), ROWS])
def test_calendar_day_when_no_matches_then_complete_empty_table(rows):
    assert on_day(Table(("A", "B", "C"), rows), "1900-01-01").rows == ()


@pytest.mark.parametrize(
    "day",
    [
        "",
        "20260320",
        "2026-02-30",
        "26-03-20",
        "2026-3-20",
        "2026-03-20T00:00:00",
        None,
        0,
        date(2026, 3, 20),
    ],
)
def test_calendar_day_when_invalid_day_then_refuse(day):
    with pytest.raises((TypeError, ValueError)):
        on_day(Table(("A", "B", "C"), ROWS), day)


@pytest.mark.parametrize(
    "stamp",
    [
        "2026-02-30 00:00:00",
        "2026-03-20",
        "2026-03-20T00:00:00",
        "2026-03-20 00:00:00+01:00",
        "2026-03-20 00:00:00.000",
        "bad",
    ],
)
def test_calendar_day_when_any_timestamp_is_invalid_then_refuse_entire_observation(
    stamp,
):
    table = Table(("A", "B", "C"), ROWS[:1] + (("bad", "", stamp),))
    with pytest.raises(ValueError):
        on_day(table, "2026-03-20")


@pytest.mark.parametrize("table", [None, [], ROWS])
def test_calendar_day_when_non_table_then_refuse(table):
    with pytest.raises(TypeError):
        on_day(table, "2026-03-20")


def test_calendar_day_when_deadline_expired_then_no_partial_result():
    with pytest.raises(TimeoutError):
        on_day(Table(("A", "B", "C"), ROWS), "2026-03-20", deadline=-1)


def test_calendar_day_when_dst_fold_then_both_local_occurrences_survive():
    rows = (("first", "", "2026-10-25 02:30:00"), ("second", "", "2026-10-25 02:30:00"))
    table = Table(("A", "B", "C"), rows, (1792888200000, 1792891800000))
    assert on_day(table, "2026-10-25") == table


def test_calendar_public_entry_when_worker_thread_then_refuse_before_widgets_load():
    with (
        ThreadPoolExecutor(max_workers=1) as pool,
        pytest.raises(RuntimeError, match="main UI thread"),
    ):
        pool.submit(show).result()


def test_calendar_entry_keeps_lazy_owned_registry_and_existing_metadata_capture(
    monkeypatch,
):
    import sys
    from types import ModuleType

    import fontlabapp.glyphs.catalog.native as native
    import fontlabapp.core.scripting as scripting_api

    module = ModuleType("fontlabapp.glyphs.calendar.ui")
    module.GlyphCalendarDialog = lambda parent, capture: (parent, capture)
    monkeypatch.setitem(sys.modules, module.__name__, module)
    monkeypatch.setattr(
        scripting_api,
        "show_script_dialog",
        lambda factory, key: (factory("owned"), key),
    )
    assert show() == (("owned", native.capture), "glyph_modification_calendar")


def test_calendar_cold_imports_remain_binding_bridge_and_host_free():
    import subprocess
    import sys

    code = """import builtins,sys
original=builtins.__import__
def guard(name,*args,**kwargs):
    assert name.split('.')[0] not in {'fontlab','fontgate','FL','PythonQt','PySide6','PyQt5','fontlab_glyport'}
    return original(name,*args,**kwargs)
builtins.__import__=guard
from fontlabapp.glyphs.calendar.model import on_day,show,show_official
from fontlabapp.qt.calendars.official.controls import Controls as OfficialControls
from fontlabapp.qt.calendars.official.formats import apply
from fontlabapp.qt.calendars.classic.controls import Controls
from fontlabapp.qt.calendars.classic.formats import first_friday
assert callable(on_day) and callable(show) and callable(show_official) and callable(Controls) and callable(OfficialControls) and callable(apply)
assert first_friday(2026,3)==6
assert not {'fontlab','fontgate','FL','PythonQt','PySide6','PyQt5','fontlab_glyport'} & sys.modules.keys()
"""
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def test_calendar_when_deadline_expires_after_render_planning_then_refuse(monkeypatch):
    import fontlabapp.glyphs.calendar.model as api

    times = iter([0, 0, 3])
    monkeypatch.setattr(api, "monotonic", lambda: next(times))
    with pytest.raises(TimeoutError):
        on_day(Table(("A", "B", "C"), ()), "2026-03-20")
