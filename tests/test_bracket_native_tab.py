# this_file: tests/test_bracket_native_tab.py
"""Both original groups use named glyph symbols and the existing fresh-tab gate."""

from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
import test_bracket_snapshot as graph_tests
import test_named_tab as tab_tests
from fontlabapp.masters.layers.brackets import native as api

native = graph_tests.native
host = tab_tests.host
named = tab_tests.named


class Symbols:
    def __init__(self, value):
        self.values = (
            [("text", value)]
            if isinstance(value, str)
            else [("glyph", s.name, s.layerName) for s in value]
        )

    def append(self, other):
        self.values.extend(other.values)


@pytest.fixture
def tab(native, monkeypatch):
    native.module.fgSymbolList = Symbols
    native.module.fgSymbol = lambda name: NS(name=name, layerName=None)
    monkeypatch.setattr(api, "_native", Mock(return_value=native.module))
    opened = Mock()
    monkeypatch.setattr(api.named_tab, "_open_symbols", opened)
    return native, opened


def test_tab_when_nested_graph_then_original_headings_and_sorted_names_in_captured_master(
    tab,
):
    source, opened = tab
    assert api.open_tab() is None
    native_module, symbols, font_id, master, _deadline = opened.call_args.args
    assert native_module is source.module and (font_id, master) == (7, "Regular")
    assert symbols.values == [
        ("text", "Glyphs:\n"),
        ("glyph", "A", "Regular"),
        ("text", "\n\nComponents:\n"),
        ("glyph", "B", "Regular"),
        ("glyph", "C", "Regular"),
    ]
    assert source.package.findFgId.call_count == 9


def test_tab_when_component_section_empty_then_no_orphan_slash_or_missing_name_filter(
    tab,
):
    source, opened = tab
    source.font.glyphs = source.font.glyphs[:1]
    source.font.glyphs[0].name = "a/unencoded"
    source.objects[1].name = "a/unencoded"
    api.open_tab()
    assert opened.call_args.args[1].values == [
        ("text", "Glyphs:\n"),
        ("glyph", "a/unencoded", "Regular"),
        ("text", "\n\nComponents:\n"),
    ]


def test_tab_when_groups_overlap_then_glyph_stays_in_both_sections(tab):
    source, opened = tab
    source.objects[2].layers[0].name = "[200]"
    api.open_tab()
    tokens = opened.call_args.args[1].values
    assert [t for t in tokens if t == ("glyph", "B", "Regular")] == [
        ("glyph", "B", "Regular")
    ] * 2


def test_tab_when_no_matches_then_original_diagnosis_and_no_new_tab(tab):
    source, opened = tab
    source.objects[1].layers[0].name = "Regular"
    with pytest.raises(
        ValueError, match="No bracket-layered glyphs or components found"
    ):
        api.open_tab()
    opened.assert_not_called()


@pytest.mark.parametrize("failure", ["symbols", "changed-graph", "shared-backend"])
def test_tab_when_build_or_recheck_fails_then_no_partial_success(
    tab, monkeypatch, failure
):
    source, opened = tab
    if failure == "symbols":
        source.module.fgSymbol = Mock(side_effect=RuntimeError("owned symbol failure"))
    elif failure == "changed-graph":
        original = source.module.fgSymbol

        def changed(name):
            source.objects[2].layers[0].shapes[0].shapeData.componentGlyph = "C"
            return original(name)

        source.module.fgSymbol = changed
    else:
        opened.side_effect = RuntimeError("owned backend failure")
    with pytest.raises((ValueError, RuntimeError)):
        api.open_tab()
    if failure != "shared-backend":
        opened.assert_not_called()


def test_report_when_capture_succeeds_then_complete_graph_without_tab(tab):
    _, opened = tab
    result = api.report()
    assert result.total == 3 and result.glyph_count == 3
    opened.assert_not_called()




@pytest.mark.parametrize(
    "mode", ["new", "unchanged", "wrong_font", "none", "population-error"]
)
def test_complete_route_when_backend_runs_then_only_fresh_target_and_flags_restored(
    native, named, monkeypatch, mode
):
    # Capture/validate the real whole-font graph, then run the actual shared
    # named/text-tab backend against independently owned native-shaped controls.
    monkeypatch.setattr(api, "_native", lambda name: named.native)
    named.state.mode = "new" if mode == "population-error" else mode
    named.state.populate_error = mode == "population-error"
    if mode in {"new", "population-error"}:
        if mode == "population-error":
            with pytest.raises(RuntimeError, match="owned populate"):
                api.open_tab()
        else:
            api.open_tab()
        values = named.state.populations[0][0].values
        assert (
            "".join(v for v in values if isinstance(v, str))
            == "Glyphs:\n\n\nComponents:\n"
        )
        assert [(v.name, v.layerName) for v in values if not isinstance(v, str)] == [
            ("A", "Regular"),
            ("B", "Regular"),
            ("C", "Regular"),
        ]
    else:
        with pytest.raises(ValueError, match="tab"):
            api.open_tab()
        assert not named.state.populations
    assert named.shape.active is False and named.old_shape.active is True
    assert named.state.calls[-2:] == ["disconnect", "delete"]
    assert native.package.findFgId.call_count == 9
