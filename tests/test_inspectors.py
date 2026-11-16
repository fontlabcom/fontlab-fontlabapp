# this_file: tests/test_inspectors.py
# SPDX-License-Identifier: Apache-2.0
"""Original inspector calculations, independent of the FontLab host."""

from importlib import import_module
from types import SimpleNamespace as NS

import pytest

api = import_module("fontlabapp.proof.inspectors.model")


@pytest.mark.parametrize(
    "values,expected",
    [
        ([], "flat"),
        ([None, 0, None], "flat"),
        ([1, 2, 2], "rising"),
        ([2, 1, 1], "falling"),
        ([1, 3, None, 2], "mixed"),
    ],
)
def test_progression_preserves_missing_zero_and_mixed(values, expected):
    assert api.progression(values) == expected


def test_width_report_keeps_order_rounding_and_missing():
    glyph = NS(
        name="a",
        findLayer={
            "Bold": NS(isNull=False, advanceWidth=0),
            "Light": NS(isNull=False, advanceWidth=10.6),
        }.get,
    )
    assert api.report([glyph], ["Light", "Absent", "Bold"]) == [
        ("a", [11, None, 0], "falling")
    ]


def test_raw_node_polygon_direction_includes_controls_and_original_start():
    nodes = [
        NS(x=x, y=y, isOn=lambda on=on: on)
        for x, y, on in [(0, 0, False), (30, 0, True), (0, 20, True)]
    ]
    contour = NS(nodes=lambda: nodes, nodesCount=3)
    layer = NS(
        autoLayer=False,
        shapes=[
            NS(isComponent=False, contours=[contour]),
            NS(isComponent=True, contours=[contour]),
        ],
    )
    assert api.contour_info(layer) == [
        (0, [(0, 0, False), (30, 0, True), (0, 20, True)], (0, 0), (30, 0), "ccw")
    ]
    assert api.layer_counts(layer) == (1, 3)
    layer.autoLayer = True
    assert api.layer_counts(layer) is None
    assert not api.incompatible({"Bold": None, "Light": (1, 3)})


def test_spacing_layout_skips_absent_layers_and_keeps_empty_advances():
    rect = NS(width=lambda: 0, height=lambda: 0, x=lambda: 0)
    layer = NS(isNull=False, advanceWidth=123, boundingBox=rect)
    glyphs = {
        "space": NS(findLayer=lambda m: layer),
        "missing": NS(findLayer=lambda m: None),
    }
    package = NS(findName=glyphs.get)
    assert api.layout(package, ["space", "missing", "space"], "Bold") == [
        ("space", 0, 123, None, None),
        ("space", 123, 123, None, None),
    ]


def test_character_and_slash_parsing_keeps_original_missing_and_delimiter_rules():
    glyphs = {
        "A": NS(name="A"),
        "space": NS(name="space"),
        "slash": NS(name="slash"),
        "alt": NS(name="alt"),
    }
    package = NS(
        findName=glyphs.get,
        findUnicode={65: glyphs["A"], 32: glyphs["space"], 47: glyphs["slash"]}.get,
    )
    assert api.parse_text("A/alt A/missing / /A/", package) == ["A", "alt", "A", "A"]
    assert api.parse_text("", package) == []
    assert api.parse_text("///", package) == []


@pytest.mark.parametrize(
    "points,expected",
    [
        ([], 0),
        ([(5, 6)], 0),
        ([(0, 0), (0, 20), (30, 0)], -300),
        ([(0, 0), (30, 0), (0, 20)], 300),
    ],
)
def test_raw_signed_area_empty_degenerate_and_both_windings(points, expected):
    assert api.signed_area(points) == expected


def test_node_counts_missing_auto_and_empty_do_not_invent_incompatibility():
    real = NS(isNull=False, autoLayer=False, shapes=[])
    auto = NS(isNull=False, autoLayer=True)
    glyph = NS(findLayer={"Regular": real, "Auto": auto}.get)
    assert api.glyph_counts(glyph, ["Missing", "Auto", "Regular"]) == {
        "Auto": None,
        "Regular": (0, 0),
    }
    assert not api.incompatible({})
    assert not api.incompatible({"a": None, "b": (0, 0)})
    assert api.incompatible({"a": (0, 0), "b": (1, 0)})


def test_negative_advances_and_nonempty_zero_width_bounds_stay_exact():
    rect = NS(x=lambda: -50, width=lambda: 0, height=lambda: 100)
    layer = NS(isNull=False, advanceWidth=-20, boundingBox=rect)
    package = NS(findName=lambda name: NS(findLayer=lambda master: layer))
    assert api.layout(package, ["a", "a"], "M") == [
        ("a", 0, -20, -50, 30),
        ("a", -20, -20, -50, 30),
    ]


def test_native_read_failures_propagate_instead_of_partial_numeric_results():
    def failed(master):
        raise RuntimeError("unreadable layer")

    glyph = NS(name="a", findLayer=failed)
    with pytest.raises(RuntimeError, match="unreadable layer"):
        api.report([glyph], ["M"])


def test_scripting_inspector_calculations_load_host_free():
    from fontlabapp.core.scripting import inspectors_api

    assert inspectors_api() is api
