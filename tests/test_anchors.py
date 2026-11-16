# this_file: tests/test_anchors.py
# SPDX-License-Identifier: Apache-2.0
"""Original anchor arithmetic, missing layers, duplicate names and raw drift."""

from importlib import import_module
from types import SimpleNamespace as NS

import pytest

api = import_module("fontlabapp.anchors.inspect.model")


def pin(name, x, y):
    return NS(name=name, point=NS(x=lambda: x, y=lambda: y))


def fixture():
    base = NS(isNull=False, autoLayer=False, anchors=[pin("top", 100.4, 700.2)])
    mark = NS(isNull=False, autoLayer=False, anchors=[pin("_top", 20.1, 30.1)])
    mixed = NS(
        isNull=False, autoLayer=True, anchors=[pin("top", 1, 2), pin("_top", 3, 4)]
    )
    glyphs = {
        "A": NS(name="A", isNull=False, findLayer={"Light": base, "Bold": mixed}.get),
        "acute": NS(name="acute", isNull=False, findLayer={"Light": mark}.get),
        "empty": NS(name="empty", isNull=False, findLayer=lambda master: None),
    }
    return NS(findName=glyphs.get), glyphs, base, mark


def test_anchor_names_cloud_frequency_rounding_and_missing_layers():
    _package, glyphs, base, _mark = fixture()
    selected = [glyphs["A"], glyphs["acute"], glyphs["empty"]]
    assert api.anchor_names(selected, ["Light", "Bold"]) == ["_top", "top"]
    assert api.cloud(selected, "Light", "top") == [("A", 100, 700)]
    base.anchors.append(pin("top", -0.6, 701.6))
    assert api.cloud(selected, "Light", "top") == [("A", 100, 700), ("A", -1, 702)]
    assert api.cloud(selected, "Absent", "top") == []
    assert api.anchor_names([], []) == []


def test_anchor_sets_keep_auto_none_and_mismatch_original_semantics():
    package, _glyphs, _base, _mark = fixture()
    rows = api.anchor_sets(
        package, ["absent", "empty", "A", "acute"], ["Light", "Bold"]
    )
    assert rows == [
        ("A", {"Light": ["top"], "Bold": None}),
        ("acute", {"Light": ["_top"]}),
    ]
    assert not api.is_mismatch(rows[0][1])
    assert api.is_mismatch({"Light": ["top"], "Bold": []})
    assert not api.is_mismatch({})


def test_mark_classification_families_offsets_and_last_duplicate_name_wins():
    package, _glyphs, base, mark = fixture()
    assert api.classify(package, ["absent", "A", "acute", "empty"], "Light") == (
        ["A"],
        ["acute"],
    )
    assert api.classify(package, ["A"], "Bold") == (["A"], ["A"])
    assert api.families(base, mark) == ["top"]
    assert api.attachment(base, mark, "top") == (80, 670)
    assert api.attachment(base, mark, "bottom") is None
    base.anchors.append(pin("top", 110, 720))
    assert api.anchor_points(base) == {"top": (110, 720)}
    assert api.attachment(base, mark, "top") == (90, 690)
    assert api.classify(package, [], "Light") == ([], [])


def test_anchor_source_keeps_raw_coordinates_auto_missing_and_geometry(monkeypatch):
    package, _glyphs, base, _mark = fixture()
    monkeypatch.setattr(
        api, "geometry_source", lambda package, names, masters, **kwargs: tuple(names)
    )
    first = api.source_values(package, ["A", "empty"], ["Light", "Bold"], ["A"])
    base.anchors[0].point.x = lambda: 100.41
    assert api.source_values(package, ["A", "empty"], ["Light", "Bold"], ["A"]) != first
    assert api.source_values(package, ["A", "empty"], ["Light", "Bold"], []) != first
    with pytest.raises(ValueError, match="Glyph source changed"):
        api.source_values(package, ["gone"], ["Light"], [])


def test_original_aliases_and_lazy_api_are_host_free():
    from fontlabapp.core.scripting import anchors_api

    assert anchors_api() is api
    for name in [
        "glyph_path",
        "selected_glyphs",
        "selected_names",
        "exact_selected_names",
        "current_package",
        "font_glyph_names",
        "pen",
        "muted",
        "frame",
        "item_ink",
    ]:
        assert callable(getattr(api, name)), name


def test_mark_selected_names_keeps_falsey_current_and_real_selection(monkeypatch):
    class Current:
        name = "A"

        def __bool__(self):
            return False

    current = Current()
    selected = []
    monkeypatch.setattr(api, "exact_selected_names", lambda: selected)
    monkeypatch.setattr(api, "_native", lambda name: NS(CurrentGlyph=lambda: current))
    assert api.selected_names() == ["A"]
    current = None
    assert api.selected_names() == []
    selected[:] = ["selected"]
    assert api.selected_names() == ["selected"]
