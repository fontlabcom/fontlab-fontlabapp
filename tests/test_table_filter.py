# this_file: tests/test_table_filter.py
"""Complete part2 custom filtering contract, independent of Qt and FontLab."""

import pytest
from fontlabapp.qt.tables.filter.model import Query, Table, sort_key


@pytest.mark.parametrize(
    "mode,pattern,text,expected",
    [
        ("regular", "a|b", "table", True),
        ("regular", "[", "x", False),
        ("regular", "", "anything", True),
        ("wildcard", "", "x", False),
        ("wildcard", "a?*", "abc", True),
        ("wildcard", "a", "ba", False),
        ("fixed", ".*", "a.*b", True),
        ("fixed", ".*", "abc", False),
        ("fixed", "STRASSE", "Straße", True),
        ("regular", "^ss$", "ß", True),
    ],
)
def test_query_when_pattern_used_then_source_engine_rules(
    mode, pattern, text, expected
):
    assert Query(pattern=pattern, syntax=mode).matches(text) is expected


def test_query_when_case_and_date_bounds_then_both_columns_or_and_inclusive_days():
    row = ("A.alt", "name <U+0041>", "2026-10-20 09:00:00")
    assert Query(pattern="0041", lower="2026-10-20", upper="2026-10-20").accepts(row)
    assert not Query(pattern="a.alt", case_sensitive=True).accepts(row)
    assert not Query(lower="2026-10-21").accepts(row)
    assert not Query(upper="2026-10-19").accepts(row)
    assert not Query(lower="2026-10-21", upper="2026-10-19").accepts(row)
    assert Query().accepts(("unencoded", "", ""))
    assert not Query(lower="2026-01-01").accepts(("unencoded", "", ""))
    assert Query(pattern="2026").accepts(row) is False, (
        "Custom matches first two columns only"
    )


def test_sort_key_when_middle_column_then_original_angle_tail_and_case_rules():
    assert sort_key("Writer <B@example>", 1, False) == "b@example"
    assert sort_key("Writer <B@example>", 0, False) == "writer <b@example>"
    assert sort_key("Writer <B@example>", 1, True) == "B@example"
    assert sort_key("A <b<c>>", 1, True) == "c"
    assert sort_key("2026-10-20", 2, False) == "2026-10-20"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"syntax": "other"},
        {"pattern": None},
        {"case_sensitive": 1},
        {"sort_sensitive": None},
        {"lower": "not-date"},
        {"upper": "2026-02-30"},
        {"lower": 2026},
        {"upper": "20261020"},
    ],
)
def test_query_when_boundary_malformed_then_refused(kwargs):
    with pytest.raises((TypeError, ValueError)):
        Query(**kwargs)


@pytest.mark.parametrize(
    "headers,rows",
    [
        (("A", "B"), ()),
        (("A", "B", "C"), [["x", "y", "z"]]),
        (("A", "B", "C"), (("x", None, "z"),)),
        (("A", "B", None), ()),
        (("A", "B", "C"), (("x", "y"),)),
    ],
)
def test_table_when_scope_malformed_then_refused(headers, rows):
    with pytest.raises((TypeError, ValueError)):
        Table(headers, rows)


def test_table_when_empty_or_valid_then_immutable_and_exact_order():
    assert Table(("A", "B", "C"), ()).rows == ()
    rows = (("b", "", ""), ("A", "U+0041", "2026-10-20"))
    assert Table(("Glyph", "Unicode", "Modified"), rows).rows == rows


def test_public_launchers_when_called_then_shared_dialog_and_exact_complete_capture(
    monkeypatch,
):
    import importlib
    from types import SimpleNamespace as NS
    from unittest.mock import Mock

    import fontlabapp.core.scripting as scripting_api
    import fontlabapp.qt.tables.filter.model as core

    launcher = importlib.import_module("fontlabapp.glyphs.catalog.model")
    ui = Mock(return_value="owned-panel")
    monkeypatch.setattr(core, "show", ui)
    assert launcher.show_basic() == "owned-panel"
    assert ui.call_args.kwargs["custom"] is False
    assert launcher.show_custom() == "owned-panel"
    assert ui.call_args.kwargs["custom"] is True
    assert ui.call_args.args[0].__module__ == "fontlabapp.glyphs.catalog.native"
    # The generic factory preserves caller capture/title/key and owns it lazily.
    import sys

    monkeypatch.setitem(
        sys.modules,
        "fontlabapp.qt.tables.filter.ui",
        NS(FilterTableDialog=Mock(return_value="widget")),
    )
    run = Mock(side_effect=lambda factory, key: (factory("parent"), key))
    monkeypatch.setattr(scripting_api, "show_script_dialog", run)
    # undo only the public call replacement, preserving this test's owned setup.
    monkeypatch.undo()
    monkeypatch.setitem(
        sys.modules,
        "fontlabapp.qt.tables.filter.ui",
        NS(FilterTableDialog=Mock(return_value="widget")),
    )
    monkeypatch.setattr(scripting_api, "show_script_dialog", run)
    capture = lambda: None
    assert core.show(
        capture, title="Title", key="owned", custom=True, description="Text"
    ) == ("widget", "owned")
    factory = sys.modules["fontlabapp.qt.tables.filter.ui"].FilterTableDialog
    assert factory.call_args.args == ("parent", "Title", "owned", capture, True, "Text")


@pytest.mark.parametrize("epochs", [(True,), [0], (0,1), (None,), (2**63,), (1.2,)])
def test_epoch_channel_when_malformed_then_refuses_before_any_qt_conversion(epochs):
    with pytest.raises((TypeError,ValueError)):
        Table(("A","B","C"), (("x","","2026-01-01 00:00:00"),), epochs=epochs)


def test_epoch_channel_when_complete_then_preserves_zero_negative_and_missing_values():
    data=Table(("A","B","C"), (("zero","","1970-01-01 00:00:00"),("old","","1969-12-31 00:00:00"),("missing","","")), epochs=(0,-86400000,None))
    assert data.epochs==(0,-86400000,None)
