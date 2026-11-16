# this_file: tests/test_tglyph_model.py
# SPDX-License-Identifier: Apache-2.0
"""Qt-free TGlyph model: reading, transform, fit, zoom, hit-testing, signature, bounds."""

import math
from types import SimpleNamespace

import pytest
from _tglyph_fakes import cyclic_font, layered_font, unsupported_layer

from fontlabapp.fontui import tglyph_model as m


def test_read_glyph_when_layered_then_contours_components_anchors():
    data = m.read_glyph(layered_font(), "a", "public.default")
    assert data.width == 500.0
    assert [c.closed for c in data.contours] == [True, False, True]
    assert [p.type for p in data.contours[0].points][:2] == ["line", "line"]
    assert data.contours[0].points[1].smooth and data.contours[0].points[1].on_curve
    assert not data.contours[0].points[2].on_curve
    assert data.anchors == (m.Anchor("top", 250.0, 600.0),)


def test_read_glyph_when_explicit_layer_then_reads_that_layer():
    data = m.read_glyph(layered_font(), "a", "Bold")
    assert data.width == 700.0 and data.contours[0].points[0].x == 20.0


def test_read_glyph_when_missing_then_key_error():
    with pytest.raises(KeyError):
        m.read_glyph(layered_font(), "b", "Bold")
    with pytest.raises(KeyError):
        m.read_glyph(layered_font(), "a", "Nope")


def test_component_when_composite_then_decomposed_on_same_layer():
    data = m.read_glyph(layered_font(), "b", "public.default")
    (component,) = data.components
    assert component.base == "a" and not component.error
    assert component.transformation == (1.0, 0.0, 0.0, 1.0, 10.0, 20.0)
    assert component.contours[0].points[0] == m.Point(10.0, 20.0, "line", False)


def test_component_when_nested_then_matrices_compose():
    font = layered_font()
    c = font.newGlyph("c")
    c.getPointPen().addComponent("b", (2, 0, 0, 2, 5, 0))
    (component,) = m.read_glyph(font, "c", "public.default").components
    assert component.contours[0].points[0].x == 25.0
    assert component.contours[0].points[0].y == 40.0


def test_component_when_cycle_or_missing_base_then_error_not_raise():
    font = layered_font()
    assert "cycle" in m.read_glyph(cyclic_font(), "loop", "public.default").components[0].error
    assert "missing" in m.read_glyph(font, "hole", "public.default").components[0].error


def test_layer_names_when_no_layer_order_then_default_only():
    assert m.layer_names(SimpleNamespace()) == ["public.default"]
    assert m.layer_names(SimpleNamespace(defaultLayerName="foreground")) == ["foreground"]
    assert m.layer_names(layered_font()) == ["public.default", "Bold"]


def test_layer_when_font_has_no_get_layer_then_default_only():
    font = {"x": 1}
    assert m._layer(font, "public.default") is font
    with pytest.raises(KeyError):
        m._layer(font, "Bold")


def test_view_when_round_trip_then_identity():
    view = m.View(scale=0.37, dx=12.0, dy=400.0)
    for x, y in ((0, 0), (123.5, -77.0), (1000, 750)):
        sx, sy = view.to_screen(x, y)
        assert view.to_font(sx, sy) == pytest.approx((x, y))
    assert view.to_screen(0, 100)[1] < view.to_screen(0, 0)[1], "font y up is screen y down"


def test_view_when_zoom_about_point_then_point_stays_fixed():
    view = m.View(scale=0.5, dx=10.0, dy=300.0)
    before = view.to_font(120.0, 80.0)
    view.zoom(m.ZOOM_STEP, 120.0, 80.0)
    assert view.scale == pytest.approx(0.5 * m.ZOOM_STEP)
    assert view.to_font(120.0, 80.0) == pytest.approx(before)
    assert view.adjusted


def test_view_when_zoom_extreme_or_invalid_then_clamped_or_ignored():
    view = m.View()
    view.zoom(1e9, 0, 0)
    assert view.scale == m.MAX_SCALE
    view.zoom(1e-12, 0, 0)
    assert view.scale == m.MIN_SCALE
    for bad in (0.0, -2.0, math.nan, math.inf):
        view.zoom(bad, 0, 0)
    assert view.scale == m.MIN_SCALE


def test_view_when_fit_then_box_centred_inside_margin():
    view = m.View()
    view.pan(5, 5)
    view.fit((0.0, -250.0, 500.0, 750.0), 400.0, 600.0)
    assert not view.adjusted
    left, top = view.to_screen(0.0, 750.0)
    right, bottom = view.to_screen(500.0, -250.0)
    assert left >= m.FIT_MARGIN - 1e-9 and right <= 400 - m.FIT_MARGIN + 1e-9
    assert top >= m.FIT_MARGIN - 1e-9 and bottom <= 600 - m.FIT_MARGIN + 1e-9
    assert (left + right) / 2 == pytest.approx(200.0) and (top + bottom) / 2 == pytest.approx(300.0)


def test_view_when_fit_degenerate_box_then_finite():
    view = m.View()
    view.fit((0.0, 0.0, 0.0, 0.0), 0.0, 0.0)
    assert math.isfinite(view.scale) and m.MIN_SCALE <= view.scale <= m.MAX_SCALE


def test_view_when_pan_then_offsets_move():
    view = m.View(dx=1.0, dy=2.0)
    view.pan(3.0, -4.0)
    assert (view.dx, view.dy, view.adjusted) == (4.0, -2.0, True)


def test_hit_point_when_within_screen_tolerance_then_nearest():
    data = m.read_glyph(layered_font(), "a", "public.default")
    view = m.View(scale=1.0, dx=0.0, dy=0.0)
    sx, sy = view.to_screen(100.0, 0.0)
    assert m.hit_point(data, view, sx + 5.0, sy) == (0, 1)
    assert m.hit_point(data, view, sx + m.HIT_TOLERANCE + 0.5, sy) is None
    assert m.hit_point(None, view, 0, 0) is None


def test_hit_point_when_zoomed_then_tolerance_stays_in_pixels():
    data = m.read_glyph(layered_font(), "a", "public.default")
    view = m.View(scale=10.0)
    sx, sy = view.to_screen(100.0, 0.0)
    assert m.hit_point(data, view, sx + 5.0, sy) == (0, 1), "5 px is 0.5 units at 10x"
    view = m.View(scale=0.1)
    sx, sy = view.to_screen(100.0, 0.0)
    assert m.hit_point(data, view, sx, sy + 7.0) is None, "7 px below the baseline misses"


def test_signature_when_points_move_then_equal_and_when_structure_changes_then_differs():
    font = layered_font()
    before = m.signature(m.read_glyph(font, "a", "public.default"))
    font["a"].moveBy((30, 40))
    assert m.signature(m.read_glyph(font, "a", "public.default")) == before
    font["a"].contours[1].appendPoint((95, 310), "line")
    assert m.signature(m.read_glyph(font, "a", "public.default")) != before
    assert m.signature(None) == ()


def test_fingerprint_when_coordinates_change_then_differs():
    font = layered_font()
    data = m.read_glyph(font, "a", "public.default")
    first = m.fingerprint(data, m.read_metrics(font))
    assert m.fingerprint(data, m.read_metrics(font)) == first
    font["a"].moveBy((1, 0))
    assert m.fingerprint(m.read_glyph(font, "a", "public.default"), m.read_metrics(font)) != first
    assert m.fingerprint(None, None, "KeyError") != m.fingerprint(None)


def test_bounds_when_outline_and_components_then_union():
    font = layered_font()
    assert m.bounds(m.read_glyph(font, "a", "public.default")) == (0.0, 0.0, 250.0, 300.0)
    assert m.bounds(m.read_glyph(font, "b", "public.default")) == (10.0, 20.0, 260.0, 320.0)
    assert m.bounds(m.read_glyph(font, "space", "public.default")) is None
    assert m.bounds(None) is None


def test_neighbour_when_stepping_then_wraps():
    order = ["a", "b", "c"]
    assert m.neighbour(order, "c", 1) == "a"
    assert m.neighbour(order, "a", -1) == "c"
    assert m.neighbour(order, "zz", 1) == "a"
    assert m.neighbour([], "a", 1) is None


def test_model_when_loaded_then_default_layer_and_order():
    model = m.TGlyphModel(layered_font())
    assert model.layer == "public.default" and model.layers() == ["public.default", "Bold"]
    assert model.glyph_order() == ["a", "b", "hole", "space"]
    model.load(None)
    assert model.data is None and model.status == "Type a glyph name."


def test_model_glyph_order_when_order_missing_then_sorted_keys():
    font = SimpleNamespace(keys=lambda: ["z", "a"])
    assert m.TGlyphModel(font).glyph_order() == ["a", "z"]
    broken = SimpleNamespace(glyphOrder=["q"], keys=None)
    assert m.TGlyphModel(broken).glyph_order() == ["q"]


def test_model_when_unknown_layer_or_glyph_then_status():
    model = m.TGlyphModel(layered_font())
    model.load("a", "Nope")
    assert model.data is None and model.status == "Layer Nope is not in this font."
    model.load("b", "Bold")
    assert model.data is None and "b is not on layer Bold" in model.status
    model.load("hole", "public.default")
    assert model.status.startswith("Component unavailable: missing")


def test_model_when_refresh_with_same_structure_then_selection_kept():
    font = layered_font()
    model = m.TGlyphModel(font)
    model.load("a")
    model.fit(400, 400)
    sx, sy = model.view.to_screen(100.0, 0.0)
    assert model.select_at(sx, sy) == (0, 1)
    view = (model.view.scale, model.view.dx, model.view.dy)
    font["a"].moveBy((5, 0))
    assert model.refresh() is False
    assert model.selection == {(0, 1)} and (model.view.scale, model.view.dx, model.view.dy) == view
    font["a"].contours[1].appendPoint((95, 310), "line")
    assert model.refresh() is True and model.selection == set()


@pytest.mark.parametrize("selection", [{(0, 0)}, {(2, 4)}, {(0, 0), (0, 4), (2, 4)}], ids=["first", "last", "multiple"])
def test_model_refresh_when_only_smooth_changes_then_selection_and_view_survive(selection):
    font = layered_font()
    model = m.TGlyphModel(font)
    model.load("a")
    model.selection = set(selection)
    model.view.zoom(1.7, 120, 80)
    model.view.pan(23, -41)
    view = vars(model.view).copy()
    before, visual = m.signature(model.data), model.fingerprint()
    point = font["a"].contours[0].points[1]
    point.smooth = not point.smooth
    assert model.fingerprint() != visual, "smoothness remains a visible change"
    assert model.refresh() is False, "smoothness does not invalidate point indices"
    assert m.signature(model.data) == before
    assert model.data.contours[0].points[1].smooth == point.smooth
    assert model.selection == selection and vars(model.view) == view


@pytest.mark.parametrize("change", ["width", "metrics", "anchor"])
def test_model_refresh_when_only_nonstructural_values_change_then_selection_survives(change):
    font = layered_font()
    model = m.TGlyphModel(font)
    model.load("a")
    model.selection = {(0, 0), (2, 4)}
    before, visual = m.signature(model.data), model.fingerprint()
    if change == "width":
        font["a"].width += 25
    elif change == "metrics":
        font.info.ascender += 25
    else:
        font["a"].anchors[0].x += 25
    assert model.fingerprint() != visual
    assert model.refresh() is False and m.signature(model.data) == before
    assert model.selection == {(0, 0), (2, 4)}


@pytest.mark.parametrize("change", ["point-count", "point-type", "open-closed", "contour-order", "component-order", "missing-glyph", "missing-layer"])
def test_model_refresh_when_structure_changes_then_selection_clears(change):
    font = layered_font()
    glyph = font["a"]
    glyph.getPointPen().addComponent("space", (1, 0, 0, 1, 0, 0))
    font.newGlyph("other")
    glyph.getPointPen().addComponent("other", (1, 0, 0, 1, 0, 0))
    model = m.TGlyphModel(font)
    model.load("a", "Bold" if change == "missing-layer" else "public.default")
    model.selection = {(0, 0), (2, 4)}
    before = m.signature(model.data)
    if change == "point-count":
        glyph.contours[1].appendPoint((95, 310), "line")
    elif change == "point-type":
        glyph.contours[0].points[-1].type = "qcurve"
    elif change == "open-closed":
        glyph.contours[1].points[0].type = "line"
    elif change == "contour-order":
        contour = glyph.contours[0].copy()
        glyph.removeContour(0)
        glyph.appendContour(contour)
    elif change == "component-order":
        component = glyph.components[0].copy()
        glyph.removeComponent(0)
        glyph.getPointPen().addComponent(component.baseGlyph, component.transformation)
    elif change == "missing-glyph":
        font.removeGlyph("a")
    else:
        font.removeLayer("Bold")
    assert model.refresh() is True
    assert m.signature(model.data) != before and model.selection == set()


@pytest.mark.parametrize("name,layer", [("b", "public.default"), ("a", "Bold"), ("missing", "public.default"), (None, "public.default")])
def test_model_load_when_target_changes_then_selection_clears(name, layer):
    model = m.TGlyphModel(layered_font())
    model.load("a")
    model.selection = {(0, 0), (2, 4)}
    model.load(name, layer)
    assert model.selection == set()
    assert (model.name, model.layer) == (name, layer)


def test_model_select_at_when_extend_then_toggles_and_miss_clears():
    model = m.TGlyphModel(layered_font())
    model.load("a")
    model.view = m.View(scale=1.0)
    first = model.view.to_screen(0.0, 0.0)
    second = model.view.to_screen(100.0, 0.0)
    model.select_at(*first)
    model.select_at(*second, extend=True)
    assert model.selection == {(0, 0), (0, 1)}
    model.select_at(*second, extend=True)
    assert model.selection == {(0, 0)}
    assert model.select_at(-500, -500, extend=True) is None and model.selection == {(0, 0)}
    model.select_at(-500, -500)
    assert model.selection == set()


def test_model_box_when_no_data_then_advance_box_from_metrics():
    model = m.TGlyphModel(layered_font())
    assert model.box() == (0.0, -200.0, 500.0, 800.0)
    model.load("a")
    assert model.box() == (0.0, -250.0, 500.0, 750.0)


def test_model_fingerprint_when_read_fails_then_error_digest():
    model = m.TGlyphModel(layered_font())
    model.load("a")
    good = model.fingerprint()
    model.name = "absent"
    assert model.fingerprint() == m.fingerprint(None, None, "KeyError") != good


def test_read_when_component_base_unsupported_then_own_contours_drawn():
    model = m.TGlyphModel(unsupported_layer(), "own")
    model.read()
    assert model.data is not None and len(model.data.contours) == 1, "own contours still draw"
    assert model.data.components[0].error.startswith("components.unresolvedBase")
    assert model.status.startswith("Component unavailable: knot (components.unresolvedBase")


def test_read_when_owner_components_unsupported_then_own_contours_via_edit_glyph_peek():
    layer = unsupported_layer(owner_raises=True)
    model = m.TGlyphModel(layer, "own")
    model.read()
    assert model.data is not None and len(model.data.contours) == 1, "own contours drawn from the staged copy"
    assert [c.base for c in model.data.components] == ["knot"] and model.data.components[0].contours == ()
    assert model.status == "Component unavailable: components.unresolvedBase: Cyclic component dependency: own"
    assert layer.edits == [], "the peek aborts the edit_glyph block, so nothing is written"
    assert model.fingerprint() == m.fingerprint(model.data, model.metrics), "fingerprint uses the same fallback"


def test_own_glyph_when_owner_unsupported_then_each_component_gets_its_own_reason():
    layer = unsupported_layer(owner_raises=True)
    own = dict.__getitem__(layer, "own")
    identity = (1, 0, 0, 1, 0, 0)
    for base in ("good", "ghost"):
        own.getPointPen().addComponent(base, identity)
    good = dict.__getitem__(layer, "knot").__class__()
    pen = good.getPointPen()
    pen.beginPath()
    for point in ((0, 0), (10, 0), (5, 10)):
        pen.addPoint(point, "line")
    pen.endPath()
    layer["good"] = good
    model = m.TGlyphModel(layer, "own")
    model.read()
    knot, healthy, ghost = model.data.components
    assert knot.error == "components.unresolvedBase: Cyclic component dependency: knot"
    assert not healthy.error and len(healthy.contours) == 1, "a healthy base still decomposes"
    assert ghost.error == "base glyph ghost is not on this layer"
    assert model.status.startswith("Component unavailable: components.unresolvedBase")


@pytest.mark.parametrize("failure", [ValueError("No layer with the name own"), RuntimeError("backend broke")])
def test_own_glyph_when_layer_cannot_be_resolved_then_peeked_data_keeps_owner_reason(failure):
    layer = unsupported_layer(owner_raises=True)

    def get_layer(name):
        raise failure

    layer.getLayer = get_layer
    data = m.own_glyph(layer, "own", "public.default", "owner reason")
    assert data is not None and len(data.contours) == 1
    assert [(c.base, c.error) for c in data.components] == [("knot", "owner reason")]


def test_edit_when_owner_components_unsupported_then_contours_written_components_kept():
    from fontlabapp.fontui import tglyph_edit as e

    layer = unsupported_layer(owner_raises=True)
    model = m.TGlyphModel(layer, "own")
    model.read()
    model.selection = {(0, 0)}
    editor = e.Editor(model)
    token = editor.commit(editor.nudge(5, 0))
    assert [u for _, _, u in layer.edits] == ["TGlyph: Nudge own"]
    raw = dict.__getitem__(layer, "own")
    assert [(p.x, p.y) for p in raw.contours[0].points][0] == (5, 0)
    assert [c.baseGlyph for c in raw.components] == ["knot"], "components untouched"
    assert token == model.fingerprint(), "echo token matches a fresh read"


def test_read_when_owner_unsupported_and_no_edit_glyph_then_status_and_nothing_editable():
    model = m.TGlyphModel(unsupported_layer(owner_raises=True, editable=False), "own")
    model.read()
    assert model.data is None
    assert model.status.endswith("; own contours unreadable, editing disabled")


def test_own_glyph_when_peek_fails_or_abort_swallowed_then_none():
    from contextlib import contextmanager

    class Broken:
        def edit_glyph(self, name, **kw):
            raise RuntimeError("closed")

    class Swallow:
        @contextmanager
        def edit_glyph(self, name, **kw):
            try:
                yield unsupported_layer()["own"]
            except Exception:
                pass

    assert m.own_glyph(Broken(), "own", "public.default", "r") is None
    assert m.own_glyph(Swallow(), "own", "public.default", "r") is None
    assert m.own_glyph(object(), "own", "public.default", "r") is None
