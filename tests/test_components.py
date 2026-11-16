# this_file: tests/test_components.py
# SPDX-License-Identifier: Apache-2.0
"""Exact original read-only component calculations, using native-shaped values."""

from importlib import import_module
from types import SimpleNamespace as NS

api = import_module("fontlabapp.components.inspect.model")


def fixture():
    transform = NS(dx=lambda: 2.6, dy=lambda: -0.5)
    comp = NS(isComponent=True, shapeData=NS(componentGlyph="A"), transform=transform)
    own = NS(isComponent=False, getContours=lambda: [1, 2])
    layer = NS(isNull=False, autoLayer=False, shapes=[comp, own])
    glyph = NS(
        name="acute",
        findLayer={
            "Bold": layer,
            "Light": NS(isNull=False, autoLayer=True, shapes=[comp]),
        }.get,
    )
    base = NS(name="A", findLayer=lambda master: None)
    return NS(findName={"acute": glyph, "A": base}.get), layer, comp


def test_complete_report_order_offset_kind_missing_and_auto():
    package, layer, comp = fixture()
    assert api.report(package, ["missing", "acute"], ["Absent", "Light", "Bold"]) == [
        ("acute", "Light", "A", "A 3,0", "auto"),
        ("acute", "Bold", "A", "A 3,0", "mixed"),
    ]
    layer.shapes.pop()
    assert api.report(package, ["acute"], ["Bold"])[0][-1] == "components"
    comp.shapeData.componentGlyph = ""
    assert api.component_rows(layer) == [("", 3, 0)]


def test_lists_reverse_index_counts_and_missing_preserve_original_interfaces():
    package, layer, comp = fixture()
    assert api.component_lists(package, ["acute"], ["Light", "Bold"]) == [
        ("acute", {"Light": ["A"], "Bold": ["A"]})
    ]
    assert api.odd_masters(
        {"Bold": [], "Light": ["A"]}, ["Absent", "Bold", "Light"]
    ) == ["Light"]
    assert api.odd_masters({}, []) == []
    assert api.counts(layer) == (1, 2, False)
    assert api.usage_index(package, ["acute"], ["Light", "Bold"]) == {
        "A": {"acute": [("Light", True), ("Bold", False)]}
    }
    assert api.missing(package, ["acute"], ["Bold"]) == {
        "A": [("acute", "Bold", "no Bold layer")]
    }
    assert api.missing(package, ["acute"], ["Bold"], exists=lambda n, m: True) == {}
    comp.shapeData.componentGlyph = ""
    assert api.missing(package, ["acute"], ["Bold"]) == {
        "(unnamed)": [("acute", "Bold", "component without a base name")]
    }
    comp.shapeData.componentGlyph = "gone"
    assert api.missing(package, ["acute"], ["Bold"]) == {
        "gone": [("acute", "Bold", "glyph missing")]
    }


def test_csv_quotes_commas_quotes_and_newlines_exactly():
    assert (
        api.to_csv([("a,b", '"x"', "one\ntwo", "", 0)])
        == 'Glyph,Master,Components,Offsets,Layer\n"a,b","""x""","one\ntwo",,0\n'
    )
    assert api.to_csv([]) == "Glyph,Master,Components,Offsets,Layer\n"


def test_empty_core_and_lazy_api():
    from fontlabapp.core.scripting import components_api

    assert components_api() is api
    assert api.report(NS(), [], []) == []
    assert api.missing(NS(), [], []) == {}
    assert api.usage_index(NS(), [], []) == {}
    assert api.component_lists(NS(), [], []) == []


def test_raw_snapshot_catches_subrounding_offset_and_base_layer_changes():
    package, _layer, comp = fixture()
    package.findName("acute").isNull = False
    transform = comp.transform
    for key, value in [("m11", 1), ("m12", 0), ("m21", 0), ("m22", 1)]:
        setattr(transform, key, lambda value=value: value)
    first = api.source_values(package, ["acute"], ["Bold"])
    transform.dx = lambda: 2.61
    assert api.source_values(package, ["acute"], ["Bold"]) != first
    transform.dx = lambda: 2.6
    package.findName("A").findLayer = lambda master: NS(isNull=False)
    assert api.source_values(package, ["acute"], ["Bold"]) != first


def test_raw_snapshot_rejects_missing_captured_glyph():
    import pytest

    with pytest.raises(ValueError, match="Glyph source changed"):
        api.source_values(NS(findName=lambda name: None), ["deleted"], ["Regular"])


def test_counts_missing_layers_duplicates_and_no_guessed_auto_counts():
    package, layer, comp = fixture()
    assert api.layer_of(package.findName("acute"), "Absent") is None
    assert not api.has_layer(package, "gone", "Bold")
    layer.shapes = [comp, comp]
    assert api.counts(layer) == (2, 0, False)
    assert api.usage_index(package, ["acute"], ["Bold"]) == {
        "A": {"acute": [("Bold", False)]}
    }
    assert api.component_lists(package, ["acute"], ["Bold"]) == [
        ("acute", {"Bold": ["A", "A"]})
    ]
    layer.shapes = []
    layer.autoLayer = True
    assert api.counts(layer) == (0, 0, True)
    assert api.report(package, ["acute"], ["Bold"]) == []


def test_original_helper_aliases_are_available_without_mock_replacements(monkeypatch):
    for name in [
        "current_package",
        "font_glyph_names",
        "selected_names",
        "selected_glyphs",
        "glyph_path",
        "current_name",
        "pen",
        "frame",
        "item_ink",
        "muted",
    ]:
        assert callable(getattr(api, name)), name
    layer, path = object(), object()
    monkeypatch.setattr(
        api, "layer_path", lambda value: path if value is layer else None
    )
    assert api.glyph_path(layer) is path


class FalseyCurrentGlyph:
    """Mirror a valid FontGate current glyph whose truth value is false."""

    name = "A"
    isNull = False

    def __bool__(self):
        return False


def test_selected_glyphs_keeps_valid_falsey_current_native_glyph(monkeypatch):
    current = FalseyCurrentGlyph()
    selected = []
    resolved = FalseyCurrentGlyph()
    monkeypatch.setattr(api, "selected_names", lambda: selected)
    natives = {
        "fontlab": NS(CurrentGlyph=lambda: current),
        "FL": NS(fl=NS(font=[], Selected=lambda index: False)),
    }
    monkeypatch.setattr(api, "_native", natives.__getitem__)
    from fontlabapp.core import scripting

    monkeypatch.setattr(scripting, "_native", natives.__getitem__)
    package = NS(findName={"A": resolved, "selected": NS(name="selected")}.get)
    assert api.selected_glyphs(package) == [resolved], (
        "A falsey native glyph is still a current glyph"
    )
    current = None
    assert api.selected_glyphs(package) == [], (
        "No current glyph must leave the grid empty"
    )
    selected[:] = ["missing", "selected"]
    assert [g.name for g in api.selected_glyphs(package)] == ["selected"], (
        "Real selection wins and unresolved names are omitted"
    )
