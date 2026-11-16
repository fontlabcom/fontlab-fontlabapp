# this_file: tests/test_node_coordinates.py
# SPDX-License-Identifier: Apache-2.0
"""Original node ordering/measurements and native-shaped active-glyph regression."""

import importlib
import math
from types import SimpleNamespace as NS

import pytest


@pytest.fixture
def api():
    return importlib.import_module("fontlabapp.contours.nodes.coordinates")


def test_current_glyph_uses_active_falsey_glyph_without_cached_workspace(
    api, monkeypatch
):
    class Glyph:
        name = "E"

        def __bool__(self):
            return False

    monkeypatch.setattr(api, "_native", lambda name: NS(CurrentGlyph=Glyph))
    glyph = object()
    assert (
        api.current_glyph(NS(findName=lambda name: glyph if name == "E" else None))
        is glyph
    )
    monkeypatch.setattr(api, "_native", lambda name: NS(CurrentGlyph=lambda: None))
    assert (
        api.current_glyph(NS(findName=lambda name: pytest.fail("No active glyph")))
        is None
    )


def test_selected_nodes_retains_own_contour_indices_and_skips_components(api):
    def node(x, selected=True, on=True):
        return NS(x=x, y=-2.5, selected=selected, isOn=lambda: on)

    a, b, handle = node(1), node(2, False), node(4, on=False)
    contours = [NS(nodes=lambda: [a, b]), NS(nodes=lambda: [handle])]
    layer = NS(
        shapes=[
            NS(isComponent=True, contours=contours),
            NS(isComponent=False, contours=contours),
        ]
    )
    assert api.selected_nodes(layer) == [(0, 0, 1, -2.5, True), (1, 0, 4, -2.5, False)]
    assert api.selected_nodes(NS(shapes=[])) == []


def test_measures_preserves_consecutive_order_angle_and_zero_length(api):
    rows = [(0, 0, 0, 0, True), (0, 3, -3, 4, False), (2, 1, -3, 4, True)]
    assert api.measures(rows) == [
        ("1:0 → 1:3", -3, 4, 5, math.degrees(math.atan2(4, -3))),
        ("1:3 → 3:1", 0, 0, 0, 0),
    ]
    assert api.measures([]) == api.measures(rows[:1]) == []


@pytest.mark.parametrize(
    "value,want",
    [(0, "0"), (-3, "-3"), (1.25, "1.2"), (-2.55, "-2.5"), (1000000, "1000000")],
)
def test_number_retains_original_rounding(api, value, want):
    assert api.number(value) == want
