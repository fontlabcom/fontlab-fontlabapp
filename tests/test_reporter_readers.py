# this_file: tests/test_reporter_readers.py
"""Offline tests for the G003 Task 2 readers: components, background, masters.

Native objects are plain fakes; ``Spy`` fakes record every native access so
the paint-safety oracle can prove no writer or mask creator is touched.
"""

import subprocess
import sys
from types import SimpleNamespace as NS

import pytest

import fontlabapp.components.decompose as decompose
from fontlabapp.glyphs import background
from fontlabapp.masters.interpolation import outlines
from fontlabapp.plugins.snapshot import _anchors, _contours
from paint_safety import Spy, assert_paint_safe, recorder


def items(get):
    return list(get())


class Point:
    def __init__(self, x, y):
        self._x, self._y = x, y

    def x(self):
        return self._x

    def y(self):
        return self._y


class QT:
    """A QTransform-like affine with getters, ``map`` and ``isAffine``."""

    def __init__(self, m11=1, m12=0, m21=0, m22=1, dx=0, dy=0, affine=True):
        self.values = (m11, m12, m21, m22, dx, dy)
        self.affine = affine

    def isAffine(self):
        return self.affine

    def map(self, point):
        a, b, c, d, e, f = self.values
        x, y = point.x(), point.y()
        return Point(x * a + y * c + e, x * b + y * d + f)

    def m11(self):
        return self.values[0]

    def m12(self):
        return self.values[1]

    def m21(self):
        return self.values[2]

    def m22(self):
        return self.values[3]

    def dx(self):
        return self.values[4]

    def dy(self):
        return self.values[5]


def contour(*points):
    """A closed contour from ``(x, y, on)`` triples."""
    nodes = [
        NS(position=Point(x, y), isOn=lambda on=on: on, selected=False)
        for x, y, on in points
    ]
    return NS(nodes=lambda: nodes, closed=True)


def outline(*points, transform=None):
    return NS(
        isComponent=False, contours=[contour(*points)], transform=transform or QT()
    )


def component(base, transform=None, layer=""):
    return NS(
        isComponent=True,
        shapeData=NS(componentGlyph=base, componentLayer=layer),
        transform=transform or QT(),
    )


def layer(*shapes, name="Regular", anchors=(), advance=500):
    return NS(
        isNull=False,
        name=name,
        shapes=list(shapes),
        anchors=list(anchors),
        advanceWidth=advance,
    )


def glyph(name, layers, stamp=1, gid=None):
    return NS(
        isNull=False,
        name=name,
        id=gid if gid is not None else hash(name) % 1000,
        lastModified=stamp,
        findLayer=lambda n: layers.get(n),
    )


def package(*glyphs, masters=("Regular",)):
    table = {g.name: g for g in glyphs}
    return NS(master="Regular", masters=list(masters), findName=table.get)


def read_components(pkg, top, shown, reported):
    return decompose.read(
        pkg,
        top.name,
        shown,
        lambda base: _contours(base, items),
        items=items,
        revision=lambda g: g.lastModified,
        report=reported.append,
    )


def points(c):
    return [(n.x, n.y, n.on_curve) for n in c.nodes]


# Components -----------------------------------------------------------------


def test_decompose_when_component_then_base_contours_are_placed_by_transform():
    base = glyph("B", {"Regular": layer(outline((0, 0, True), (10, 0, True)))})
    shown = layer(component("B", QT(dx=100, dy=5)))
    top = glyph("A", {"Regular": shown})
    reported = []
    rows, stamps = read_components(package(top, base), top, shown, reported)
    assert [(name, transform) for name, transform, _ in rows] == [
        ("B", (1.0, 0.0, 0.0, 1.0, 100.0, 5.0))
    ]
    assert [points(c) for c in rows[0][2]] == [[(100, 5, True), (110, 5, True)]]
    assert stamps == (("B", 1),)
    assert reported == []


def test_decompose_when_base_nodes_selected_then_component_nodes_are_not():
    base_shape = outline((0, 0, True))
    base_shape.contours[0].nodes()[0].selected = True  # selected in another window
    base = glyph("B", {"Regular": layer(base_shape)})
    shown = layer(component("B"))
    top = glyph("A", {"Regular": shown})
    rows, _ = read_components(package(top, base), top, shown, [])
    assert rows[0][2][0].nodes[0].selected is False


def test_snapshot_import_when_plugmix_loads_then_component_facade_stays_unloaded():
    code = (
        "import sys, fontlabapp.plugins.snapshot; "
        "print('fontlabapp.components.inspect.model' in sys.modules)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "False", "the legacy facade must stay lazy"


def test_decompose_when_nested_then_inner_then_outer_transform_apply():
    inner = glyph("C", {"Regular": layer(outline((1, 0, True)))})
    middle = glyph("B", {"Regular": layer(component("C", QT(dx=10)))})
    shown = layer(component("B", QT(m11=2, m22=2)))
    top = glyph("A", {"Regular": shown})
    rows, stamps = read_components(package(top, middle, inner), top, shown, [])
    # Translate then scale gives (1+10)*2 = 22; the reverse order would give 12.
    assert [points(c) for c in rows[0][2]] == [[(22, 0, True)]]
    assert dict(stamps) == {"B": 1, "C": 1}


def test_decompose_when_base_used_twice_or_diamond_then_no_cycle_is_reported():
    dot = glyph("dot", {"Regular": layer(outline((0, 0, True)))})
    left = glyph("L", {"Regular": layer(component("dot"))})
    right = glyph("R", {"Regular": layer(component("dot", QT(dx=1)))})
    shown = layer(
        component("dot"), component("dot", QT(dy=9)), component("L"), component("R")
    )
    top = glyph("colon", {"Regular": shown})
    reported = []
    rows, _ = read_components(package(top, dot, left, right), top, shown, reported)
    assert [name for name, _, _ in rows] == ["dot", "dot", "L", "R"]
    assert [points(c) for c in rows[1][2]] == [[(0, 9, True)]]
    assert [points(c) for c in rows[3][2]] == [[(1, 0, True)]]
    assert reported == []


def test_decompose_when_self_reference_or_cycle_then_skipped_and_reported_once():
    shown = layer(component("A"), component("A"), outline((0, 0, True)))
    top = glyph("A", {"Regular": shown})
    reported = []
    rows, _ = read_components(package(top), top, shown, reported)
    assert rows == ()
    assert len(reported) == 1 and "cycle" in str(reported[0])
    loop_b = glyph("B", {"Regular": layer(component("C"))})
    loop_c = glyph("C", {"Regular": layer(component("B"), outline((5, 5, True)))})
    shown = layer(component("B"))
    top = glyph("A", {"Regular": shown})
    reported = []
    rows, _ = read_components(package(top, loop_b, loop_c), top, shown, reported)
    assert [points(c) for c in rows[0][2]] == [[(5, 5, True)]], "B keeps C's outline"
    assert len(reported) == 1 and "'B'" in str(reported[0])


def test_decompose_when_deeper_than_limit_then_cut_and_reported():
    depth = decompose.MAX_DEPTH
    chain = [
        glyph(
            f"g{i}", {"Regular": layer(component(f"g{i + 1}"), outline((i, 0, True)))}
        )
        for i in range(1, depth + 2)
    ]
    shown = layer(component("g1"))
    top = glyph("g0", {"Regular": shown})
    reported = []
    rows, _ = read_components(package(top, *chain), top, shown, reported)
    xs = sorted(points(c)[0][0] for c in rows[0][2])
    assert xs == list(range(1, depth + 1)), f"{depth} nesting levels are decomposed"
    assert len(reported) == 1 and f"g{depth + 1}" in str(reported[0])


def test_decompose_when_base_missing_then_skipped_and_reported_once():
    shown = layer(component("nope"), component("nope", QT(dx=3)))
    top = glyph("A", {"Regular": shown})
    reported = []
    rows, stamps = read_components(package(top), top, shown, reported)
    assert rows == ()
    assert len(reported) == 1 and "'nope'" in str(reported[0])
    assert stamps == (("nope", None),), "a later glyph can invalidate the cache"


def test_decompose_when_layer_named_or_empty_then_empty_means_owner_master():
    base = glyph(
        "B",
        {
            "Regular": layer(outline((1, 1, True))),
            "Alt": layer(outline((2, 2, True)), name="Alt"),
            "Brace": layer(outline((3, 3, True)), name="Brace"),
        },
    )
    shown = layer(component("B", layer="Alt"), component("B"), name="Brace")
    top = glyph("A", {"Brace": shown})
    rows, _ = read_components(package(top, base), top, shown, [])
    # "Brace" is not a master, so an empty reference means package.master.
    assert [points(r[2][0]) for r in rows] == [[(2, 2, True)], [(1, 1, True)]]
    empty = glyph("E", {})
    shown = layer(component("E"))
    reported = []
    assert read_components(package(top, empty), top, shown, reported)[0] == ()
    assert len(reported) == 1 and "'E'" in str(reported[0])


def test_decompose_when_shown_layer_is_mask_then_empty_reference_uses_master():
    base = glyph(
        "B",
        {
            "Regular": layer(outline((1, 1, True))),
            "mask.Regular": layer(outline((9, 9, True)), name="mask.Regular"),
        },
    )
    shown = layer(component("B"), name="mask.Regular")
    top = glyph("A", {"mask.Regular": shown})
    rows, _ = read_components(package(top, base), top, shown, [])
    assert [points(c) for c in rows[0][2]] == [[(1, 1, True)]], "never the mask"


def test_decompose_when_shown_layer_is_other_master_then_it_owns_empty_names():
    base = glyph(
        "B",
        {
            "Regular": layer(outline((1, 1, True))),
            "Bold": layer(outline((5, 5, True)), name="Bold"),
        },
    )
    shown = layer(component("B"), name="Bold")
    top = glyph("A", {"Bold": shown})
    pkg = package(top, base, masters=("Regular", "Bold"))
    rows, _ = read_components(pkg, top, shown, [])
    assert [points(c) for c in rows[0][2]] == [[(5, 5, True)]]


def test_decompose_when_nested_name_given_then_it_is_not_passed_down():
    inner = glyph(
        "C",
        {
            "Regular": layer(outline((1, 0, True))),
            "Alt": layer(outline((2, 0, True)), name="Alt"),
        },
    )
    middle = glyph("B", {"Alt": layer(component("C"), name="Alt")})
    shown = layer(component("B", layer="Alt"))
    top = glyph("A", {"Regular": shown})
    rows, _ = read_components(package(top, middle, inner), top, shown, [])
    assert [points(c) for c in rows[0][2]] == [[(1, 0, True)]], "C's empty is Regular"


def test_decompose_when_named_layer_missing_then_skipped_without_fallback():
    base = glyph("B", {"Regular": layer(outline((1, 1, True)))})
    shown = layer(component("B", layer="Alt"))
    top = glyph("A", {"Regular": shown})
    reported = []
    assert read_components(package(top, base), top, shown, reported)[0] == ()
    assert len(reported) == 1 and "'Alt'" in str(reported[0])


def test_decompose_when_transform_not_affine_then_skipped_and_reported():
    base = glyph("B", {"Regular": layer(outline((0, 0, True)))})
    shown = layer(component("B", QT(affine=False)), component("B"))
    top = glyph("A", {"Regular": shown})
    reported = []
    rows, _ = read_components(package(top, base), top, shown, reported)
    assert len(rows) == 1
    assert len(reported) == 1 and "affine" in str(reported[0])


def test_decompose_when_attribute_missing_then_raises():
    shown = layer(NS(isComponent=True, transform=QT()))
    top = glyph("A", {"Regular": shown})
    with pytest.raises(AttributeError):
        read_components(package(top), top, shown, [])


def test_decompose_reads_without_unsafe_native_calls():
    log = []
    base_layer = Spy(
        log, "base", isNull=False, name="Regular", shapes=[outline((0, 0, True))]
    )
    base = Spy(
        log,
        "baseGlyph",
        isNull=False,
        lastModified=3,
        findLayer=recorder(log, "baseGlyph", "findLayer", base_layer),
    )
    pkg = Spy(
        log,
        "package",
        master="Regular",
        masters=["Regular"],
        findName=recorder(log, "package", "x", base),
    )
    shown = Spy(log, "layer", name="Regular", shapes=[component("B")])
    rows, _ = decompose.read(
        pkg,
        "A",
        shown,
        lambda base_layer: _contours(base_layer, items),
        items=items,
        revision=lambda g: g.lastModified,
        report=lambda e: pytest.fail(str(e)),
    )
    assert len(rows) == 1
    assert_paint_safe(log)


# Background -----------------------------------------------------------------


def mask_fixture(log, *, mask_glyph_id=7, auto=False, valid=True, mask=True):
    mask_layer = Spy(
        log,
        "mask",
        isNull=False,
        isValid=valid,
        autoLayer=auto,
        glyph=NS(id=mask_glyph_id),
        shapes=[outline((4, 4, True))],
    )
    fg = Spy(
        log,
        "layer",
        isMaskLayer=False,
        getMaskLayer=recorder(
            log, "layer", "getMaskLayer", mask_layer if mask else None
        ),
    )
    return NS(id=7), fg


def read_background(g, fg, reported):
    return background.read(g, fg, lambda m: _contours(m, items), reported.append)


def test_background_when_mask_exists_then_reads_it_through_get_mask_layer_false():
    log, reported = [], []
    g, fg = mask_fixture(log)
    shapes = read_background(g, fg, reported)
    assert [points(c) for c in shapes] == [[(4, 4, True)]]
    assert reported == []
    assert ("layer", "call", "getMaskLayer", (False,)) in log
    assert_paint_safe(log, allowed={("layer", "getMaskLayer", (False,))})
    assert not [e for e in log if e[0] == "mask" and e[1] == "call"]


def test_background_when_no_mask_or_null_or_invalid_then_none():
    log = []
    assert read_background(*mask_fixture(log, mask=False), []) is None
    assert read_background(*mask_fixture(log, valid=False), []) is None
    g, fg = mask_fixture(log)
    fg._attrs["getMaskLayer"] = recorder(log, "layer", "getMaskLayer", NS(isNull=True))
    assert read_background(g, fg, []) is None


def test_background_when_empty_mask_then_empty_tuple_not_none():
    log = []
    g, fg = mask_fixture(log)
    empty = NS(isNull=False, isValid=True, autoLayer=False, glyph=NS(id=7), shapes=[])
    fg._attrs["getMaskLayer"] = recorder(log, "layer", "getMaskLayer", empty)
    assert read_background(g, fg, []) == ()


def test_background_when_shown_layer_is_a_mask_then_never_asks_it_for_a_mask():
    log = []
    shown = Spy(log, "layer", isMaskLayer=True)
    assert read_background(NS(id=7), shown, []) is None
    assert_paint_safe(log)


def test_background_when_foreign_or_automatic_then_skipped_and_reported():
    for kwargs in ({"mask_glyph_id": 99}, {"auto": True}):
        log, reported = [], []
        assert read_background(*mask_fixture(log, **kwargs), reported) is None
        assert len(reported) == 1 and isinstance(reported[0], ValueError)


def test_paint_safety_oracle_when_mask_created_or_mask_asked_then_fails():
    with pytest.raises(AssertionError):
        assert_paint_safe(
            [("layer", "call", "getMaskLayer", (True,))],
            allowed={("layer", "getMaskLayer", (False,))},
        )
    with pytest.raises(AssertionError):
        assert_paint_safe(
            [("mask", "get", "getMaskLayer")],
            allowed={("layer", "getMaskLayer", (False,))},
        )
    with pytest.raises(AssertionError):
        assert_paint_safe([("layer", "get", "getMaskLayer")])


# Masters --------------------------------------------------------------------


def read_masters(pkg, g, shown_contours):
    return outlines.read(
        pkg,
        g,
        shown_contours,
        lambda m: _contours(m, items),
        lambda m: _anchors(m, items),
        items=items,
    )


def test_masters_when_read_then_every_master_in_order_with_compatibility():
    regular = layer(
        outline((0, 0, True), (5, 5, False), (9, 0, True)),
        anchors=[NS(name="top", point=Point(4, 9))],
        advance=500,
    )
    bold = layer(outline((0, 0, True), (7, 7, False), (12, 0, True)), advance=600)
    odd = layer(outline((0, 0, True), (7, 7, True), (12, 0, True)))
    short = layer(outline((0, 0, True), (12, 0, True)))
    extra = layer(outline((0, 0, True)), outline((1, 1, True)))
    g = glyph(
        "A",
        {"Regular": regular, "Bold": bold, "Odd": odd, "Short": short, "X": extra},
    )
    pkg = package(g, masters=("Regular", "Bold", "Missing", "Odd", "Short", "X"))
    rows = read_masters(pkg, g, _contours(regular, items))
    assert [(r[0], r[4]) for r in rows] == [
        ("Regular", True),
        ("Bold", True),
        ("Odd", False),
        ("Short", False),
        ("X", False),
    ], "on/off pattern, node count and contour count all decide compatibility"
    name, shapes, anchors, advance, _ = rows[1]
    assert (name, advance, anchors) == ("Bold", 600.0, ())
    assert points(shapes[0]) == [(0, 0, True), (7, 7, False), (12, 0, True)]
    assert [(a.name, a.x, a.y) for a in rows[0][2]] == [("top", 4.0, 9.0)]


def test_masters_when_layer_attribute_missing_then_raises():
    broken = NS(isNull=False, shapes=[], anchors=[])
    g = glyph("A", {"Regular": broken})
    with pytest.raises(AttributeError):
        read_masters(package(g), g, ())


def test_masters_reads_without_unsafe_native_calls():
    log = []
    shown = layer(outline((0, 0, True)))
    g = Spy(log, "glyph", findLayer=recorder(log, "glyph", "findLayer", shown))
    pkg = Spy(log, "package", masters=["Regular", "Bold"])
    rows = read_masters(pkg, g, _contours(shown, items))
    assert [r[0] for r in rows] == ["Regular", "Bold"]
    assert ("glyph", "call", "findLayer", ("Bold",)) in log
    assert_paint_safe(log)
