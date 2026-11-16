# this_file: tests/test_contour_selection_native.py
"""Real public adapters against owned native-shaped geometry and selection."""

from types import SimpleNamespace as NS

import pytest

import fontlabapp.contours.selection.native as native
import fontlabapp.contours.selection.model as api


class Item:
    def __init__(self, ident, selected=False, kind=1043):
        self.id, self._selected, self.type = ident, selected, kind
        self.smart, self.calls, self.fail = True, [], False

    @property
    def selected(self):
        return self._selected

    @selected.setter
    def selected(self, value):
        self.calls.append(value)
        self._selected = value
        if not value:
            self.smart = False
        if self.fail:
            self.fail = False
            raise RuntimeError("owned setter failure")

    @property
    def nodeState(self):
        return 1 | (native.SELECTED if self.selected else 0)

    def getProperty(self, key):
        return self.smart

    def setProperty(self, key, value):
        self.smart = value


def transform(scale=1):
    return NS(
        **{
            name: lambda value=value: value
            for name, value in zip(
                ("m11", "m12", "m13", "m21", "m22", "m23", "m31", "m32", "m33"),
                (scale, 0, 0, 0, scale, 0, 0, 0, 1),
            )
        },
        map=lambda point: NS(x=lambda: point[0] * scale, y=lambda: point[1] * scale),
        isAffine=lambda: True,
    )


@pytest.fixture
def source(monkeypatch):
    rows, contours = [], []
    for index, flags in enumerate(((False, True, False), (False, False, True, False))):
        row = [Item(index * 10 + i, selected) for i, selected in enumerate(flags)]
        for i, node in enumerate(row):
            node.x, node.y = i, index
        rows.append(row)
        contours.append(
            NS(
                id=100 + index,
                nodes=lambda row=row: row,
                closed=index == 0,
                isTT=index == 1,
                segments=lambda: [((0, 0), (10, 0)), ((10, 0), (10, 10))],
            )
        )
    shape = Item(200, True, 1022)
    shape.isComponent, shape.transform, shape.contours = False, transform(), contours
    component = Item(201, True, 1022)
    component.isComponent, component.transform, component.contours = (
        True,
        transform(),
        [],
    )
    anchor = Item(202, True)
    layer = NS(
        shapes=[shape, component], transform=transform(), anchors=[], guidelines=[]
    )
    occurrence = NS(
        layer=layer, package_id=1, glyph_id=2, layer_id=3, block_id=4, index=0
    )
    block = NS(glyphsCount=lambda: 1)
    canvas = NS(
        selection=lambda: [anchor] if anchor.selected else [], textBlocks=[block]
    )
    selected = NS(
        context=(1, "Regular", "editor"), occurrences=[occurrence], carriers=[canvas]
    )
    monkeypatch.setattr(native.layer_selection, "capture", lambda deadline: selected)
    return NS(
        rows=rows,
        contours=contours,
        layer=layer,
        shape=shape,
        component=component,
        anchor=anchor,
        canvas=canvas,
        block=block,
        selected=selected,
    )


def flags(source):
    return tuple(tuple(node.selected for node in row) for row in source.rows)


def test_public_full_selects_controls_and_preserves_other_selection(source):
    assert api.select_contours() == 2
    assert flags(source) == ((True, True, True), (True, True, True, True))
    assert source.anchor.selected and source.component.selected
    assert api.select_contours() == 2
    assert all(len(node.calls) <= 1 for row in source.rows for node in row)


def test_public_partial_matches_original_cross_contour_sequence(source):
    assert api.select_partial_contours() == 2
    assert flags(source) == ((False, True, True), (True, True, True, False))
    assert source.anchor.selected and source.component.selected


def test_public_small_clears_nodes_components_and_anchor_then_selects_strict_area(
    source,
):
    assert api.select_small_contours(50) == 0
    assert not any(any(row) for row in flags(source))
    assert not source.anchor.selected and not source.component.selected
    assert api.select_small_contours(51) == 2
    assert all(all(row) for row in flags(source))


def test_shape_transform_scales_area_without_changing_native_geometry(source):
    source.shape.transform = transform(2)
    snapshot = native.capture(area=True)
    assert tuple(path.area for path in snapshot.paths) == (200, 200)


@pytest.mark.parametrize(
    "change", ["context", "geometry", "selected", "closed", "master"]
)
def test_stale_context_refuses_before_any_setter(source, change):
    snapshot = native.capture()
    if change in ("context", "master"):
        source.selected.context = (2, "Bold", "editor")
    elif change == "geometry":
        source.rows[0][0].x = 100
    elif change == "closed":
        source.contours[0].closed = False
    else:
        source.rows[0][0]._selected = True
    with pytest.raises(ValueError, match="changed"):
        native.execute("contours", source=snapshot)
    assert not any(node.calls for row in source.rows for node in row)


@pytest.mark.parametrize(
    "location", ["node", "second-node", "anchor", "shape", "component"]
)
def test_late_setter_failure_restores_attempted_flags_and_smart_state(source, location):
    before = flags(source)
    failing = {
        "node": source.rows[0][1],
        "second-node": source.rows[1][2],
        "anchor": source.anchor,
        "shape": source.shape,
        "component": source.component,
    }[location]
    failing.fail = True
    with pytest.raises(RuntimeError, match="restoration completed"):
        api.select_small_contours(0)
    assert flags(source) == before
    assert source.anchor.selected and source.shape.selected
    if location == "node":
        assert failing.smart


def test_missing_selection_and_ambiguous_mixed_canvas_refuse(source):
    source.selected.occurrences = []
    with pytest.raises(ValueError, match="Select a glyph"):
        api.select_contours()
    source.selected.occurrences = [
        NS(
            layer=source.layer,
            package_id=1,
            glyph_id=2,
            layer_id=3,
            block_id=4,
            index=0,
        )
    ]
    source.block.glyphsCount = lambda: 2
    with pytest.raises(ValueError, match="ownership support"):
        api.select_small_contours(51)
    api.select_partial_contours()


def test_unknown_visual_item_refuses_small_but_other_actions_preserve_it(source):
    source.anchor.type = 1027
    with pytest.raises(ValueError, match="native item"):
        api.select_small_contours(51)
    api.select_contours()
    assert source.anchor.selected


def test_font_window_and_empty_paths_are_supported(source):
    source.selected.context = (1, "Regular", "font")
    source.contours[0].nodes = lambda: []
    source.contours[0].segments = lambda: []
    assert api.select_small_contours(1) == 1


def test_deadline_and_bad_plan_refuse(source, monkeypatch):
    snapshot = native.capture()
    with pytest.raises(ValueError, match="topology"):
        native.apply(snapshot, api.Plan((), 0))
    monkeypatch.setattr(native, "monotonic", iter((0, 3)).__next__)
    with pytest.raises(TimeoutError):
        native.capture()


def test_font_window_mixed_anchor_or_guides_refuses_before_setters(source):
    source.selected.context = (1, "Regular", "font")
    source.layer.anchors = [object()]
    with pytest.raises(ValueError, match="Glyph window"):
        api.select_small_contours(51)
    assert not source.shape.calls


def test_getter_failure_refuses_without_touching_selection(source):
    source.contours[1].nodes = lambda: (_ for _ in ()).throw(
        RuntimeError("owned getter failure")
    )
    with pytest.raises(RuntimeError, match="owned getter"):
        api.select_contours()
    assert not source.shape.calls
    assert not any(node.calls for row in source.rows for node in row)


def test_projective_area_refuses_without_approximating_a_rational_curve(source):
    source.shape.transform.isAffine = lambda: False
    with pytest.raises(ValueError, match="affine shape"):
        api.select_small_contours(50)
    assert source.anchor.selected
    assert not source.shape.calls


def test_rollback_error_is_explicit_and_retains_partial_status(source, monkeypatch):
    source.rows[0][1].fail = True
    monkeypatch.setattr(
        source.rows[0][1],
        "setProperty",
        lambda *args: (_ for _ in ()).throw(RuntimeError("smart restore failed")),
    )
    with pytest.raises(RuntimeError, match="restoration failed:.*smart restore failed"):
        api.select_small_contours(0)


def test_missing_pens_fails_before_any_clearing(source, monkeypatch):
    import builtins

    original = builtins.__import__

    def without_pens(name, *args, **kwargs):
        if name == "fontlab_pens":
            raise ImportError("owned missing dependency")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_pens)
    with pytest.raises(ImportError, match="owned missing dependency"):
        api.select_small_contours(10)
    assert not source.shape.calls
    assert not any(node.calls for row in source.rows for node in row)
