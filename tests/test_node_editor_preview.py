# this_file: tests/test_node_editor_preview.py
"""Detached previews retain open endpoints and source coordinates."""
from types import SimpleNamespace as NS

import pytest

from fontlabapp.fontui.node_editor.preview import literal, per_glyph
from fontlabapp.fontui.tglyph_model import GlyphData, Contour, Point
from fontlabapp.contours.nodes.duplicator.model import Node, Path, Layer, Source, plan


def test_literal_preview_matches_planned_topology_without_mutating_source():
    node = Node(1, 10, 20, "line", 8, "a", ())
    path = Path(2, (node,), False)
    source = Source((Layer(3, 4, (path,), True),), (3,), ((0, 1),), True)
    before = NS(source=source)
    result = plan(source, "handles")
    data = GlyphData("a", "Regular", 500, (Contour((Point(110, 220, "move", True),)),))
    drawn = literal(data, before, result, 3)
    assert len(drawn.contours[0].points) == 4
    assert [p.type for p in drawn.contours[0].points] == ["move", None, None, "curve"]
    assert all((p.x, p.y) == (110, 220) for p in drawn.contours[0].points)
    assert len(data.contours[0].points) == 1
    with pytest.raises(ValueError, match="topology"):
        literal(None, before, result, 3)
    with pytest.raises(ValueError, match="order"):
        literal(GlyphData("a", "Regular", contours=(Contour(()),)), before, result, 3)


@pytest.mark.parametrize("handles,count", [(False, 2), (True, 4)])
def test_per_glyph_preview_keeps_component_contours_outside_scope(handles, count):
    contour = object()
    layer = NS(shapes=[NS(isComponent=True), NS(isComponent=False, contours=[contour])])
    data = GlyphData("a", "Regular", contours=(Contour((Point(1, 2, "move"),)),))
    overlay = per_glyph(data, layer, [(contour, (0,), handles)])
    assert len(overlay.contours[0].points) == count
    assert overlay.contours[0].points[0].type == "move"
    assert len(data.contours[0].points) == 1
    with pytest.raises(ValueError, match="topology"):
        per_glyph(None, layer, [])
