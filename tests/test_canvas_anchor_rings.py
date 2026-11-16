# this_file: tests/test_canvas_anchor_rings.py
"""Independent numerical and borrowed-Qt oracles for duplicate anchor rings."""

import importlib
import math
from dataclasses import FrozenInstanceError
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from PySide6 import QtCore, QtGui

from fontlabapp.metrics.canvas_rsb.model import map_point

api = importlib.import_module("fontlabapp.anchors.canvas_rings.model")


@pytest.mark.parametrize(
    "points,count",
    [
        ([], 0),
        ([(0, 0)], 0),
        ([(0, 0), (0.99, 0)], 1),
        ([(0, 0), (1, 0)], 0),
        ([(0, 0), (1.01, 0)], 0),
        ([(0, 0)] * 3, 3),
        ([(0, 0), (0.6, 0.8)], 0),
    ],
)
def test_strict_euclidean_pair_threshold_retains_every_pair(points, count):
    rings = api.rings(tuple(points), 1)
    assert len(rings) == count, "Strict distance<1.0 or pair multiplicity changed"
    if count == 3:
        assert [r.pair for r in rings] == [(0, 1), (0, 2), (1, 2)]


@pytest.mark.parametrize("handle", [5, 8, 12])
def test_original_handle_diameter_and_two_stroke_scales(handle):
    (ring,) = api.rings(((20, 30), (20.1, 30)), 2, handle_size=handle)
    assert ring.center == (20, 30), "Marker moved away from first pair position"
    assert ring.diameter == pytest.approx(2 * handle * 2**-0.9)
    assert (ring.outer, ring.inner) == (3, 1), "Original6/scale,2/scale widths lost"
    with pytest.raises(FrozenInstanceError):
        ring.outer = 99


@pytest.mark.parametrize(
    "points,scale,handle",
    [
        (((math.nan, 0),), 1, 8),
        (((0, math.inf),), 1, 8),
        ((), 0, 8),
        ((), -1, 8),
        ((), math.nan, 8),
        ((), 1, 9),
    ],
)
def test_invalid_numeric_inputs_refuse_even_without_pairs(points, scale, handle):
    with pytest.raises(ValueError):
        api.rings(points, scale, handle_size=handle)


def test_pair_search_obeys_deadline_without_partial_results():
    with pytest.raises(TimeoutError):
        api.rings(((0, 0), (0, 0)), 1, deadline=0)


@pytest.fixture
def scene(monkeypatch):
    qt = NS(QtCore=QtCore, QtGui=QtGui)
    monkeypatch.setattr(api, "_native", lambda name: qt)
    package = NS(id=7, master="Regular", masters=["Regular", "Bold"])
    pins = [
        NS(name="top", point=QtCore.QPointF(20, 30)),
        NS(name="bottom", point=QtCore.QPointF(20.5, 30)),
    ]
    layer = NS(isNull=False, anchors=pins)
    glyph = NS(id=31, name="H", isNull=False, findLayer=lambda master: layer)
    infos = [
        NS(
            id=41,
            glyph=glyph,
            isActive=True,
            transform=QtGui.QTransform.fromTranslate(40, 50),
        ),
        NS(
            id=42,
            glyph=glyph,
            isActive=False,
            transform=QtGui.QTransform.fromTranslate(615, 50),
        ),
    ]
    block = NS(
        id=51,
        package=package,
        transform=QtGui.QTransform(2, 0, 0, 2, 100, 200),
        getAllGlyphs=lambda: infos,
    )
    canvas = NS(
        id=61,
        textBlocks=lambda: [block],
        mapToViewportF=lambda p: QtCore.QPointF(3 * p.x() + 7, -3 * p.y() + 11),
    )
    return package, pins, layer, glyph, infos, block, canvas


def test_repeated_native_occurrences_keep_complete_numeric_context_and_maps(scene):
    package, pins, _layer, _glyph, infos, block, canvas = scene
    snap = api.capture(canvas, package)
    assert (snap.package_id, snap.canvas_id, snap.master) == (7, 61, "Regular")
    assert snap.masters == ("Regular", "Bold")
    assert [o.item for o in snap.occurrences] == [(51, 41), (51, 42)]
    assert [o.active for o in snap.occurrences] == [True, False]
    first, second = snap.occurrences
    a = map_point(first.transform, first.rings[0].center)
    b = map_point(second.transform, second.rings[0].center)
    assert a == (667, -1069), "Wrong glyph×block×viewport order"
    assert b[0] - a[0] == 575 * 6, "Kerning already lives in glyph placement"
    assert first.glyph_id == 31 and first.rings[0].diameter == pytest.approx(
        16 * 6**-0.9
    )
    pins[0].point = QtCore.QPointF(99, 99)
    infos[0].id = 99
    block.id = 99
    assert first.anchors[0] == ("top", (20, 30))
    assert first.item == (51, 41), "Snapshot retained mutable wrappers"
    with pytest.raises(FrozenInstanceError):
        snap.master = "Bold"


def test_empty_and_foreign_sources_still_keep_binding(scene):
    package, _pins, layer, _glyph, _infos, block, canvas = scene
    layer.anchors = []
    snap = api.capture(canvas, package)
    assert len(snap.occurrences) == 2 and not snap.occurrences[0].rings
    block.package = NS(id=99)
    assert api.capture(canvas, package).occurrences == ()
    block.package = package
    block.getAllGlyphs = lambda: None
    assert api.capture(canvas, package).occurrences == ()


@pytest.mark.parametrize(
    "fault",
    [
        "layer",
        "glyph",
        "master",
        "domain",
        "canvas",
        "transform",
        "viewport",
        "deadline",
    ],
)
def test_capture_refuses_stale_invalid_or_incomplete_scans(scene, fault):
    package, _pins, layer, _glyph, infos, block, canvas = scene
    if fault == "layer":
        layer.isNull = True
    elif fault == "glyph":
        infos[0].glyph = None
    elif fault in ("master", "domain", "canvas"):

        def mutate():
            if fault == "master":
                package.master = "Bold"
            elif fault == "domain":
                package.masters.append("Other")
            else:
                canvas.id = 99
            return [block]

        canvas.textBlocks = mutate
    elif fault == "transform":
        infos[0].transform = QtGui.QTransform(0, 0, 0, 0, 0, 0)
    elif fault == "viewport":
        canvas.mapToViewportF = lambda p: QtCore.QPointF(math.nan, 0)
    with pytest.raises((ValueError, TimeoutError)):
        api.capture(canvas, package, **({"deadline": 0} if fault == "deadline" else {}))


def test_paint_uses_original_colors_and_restores_borrowed_painter_on_failure(scene):
    package, *_others, canvas = scene
    snapshot = api.capture(canvas, package)
    painter = Mock()
    api.paint(painter, snapshot)
    assert painter.drawEllipse.call_count == 4
    assert painter.save.call_count == painter.restore.call_count == 2
    assert [c.args[0].color().getRgb() for c in painter.setPen.call_args_list] == [
        (255, 0, 0, 255),
        (255, 255, 0, 255),
    ] * 2
    painter.end.assert_not_called()
    painter.drawEllipse.side_effect = ValueError("paint injected")
    with pytest.raises(ValueError, match="paint injected"):
        api.paint(painter, snapshot)
    assert painter.save.call_count == painter.restore.call_count


def test_native_capture_is_not_reentered_by_paint(scene, monkeypatch):
    package, *_others, canvas = scene
    snapshot = api.capture(canvas, package)
    monkeypatch.setattr(api, "capture", Mock(side_effect=AssertionError("native read")))
    canvas.textBlocks = Mock(side_effect=AssertionError("native read"))
    api.paint(Mock(), snapshot)
    canvas.textBlocks.assert_not_called()


def test_extreme_scale_refuses_nonfinite_ring_dimensions():
    with pytest.raises(ValueError, match="dimensions"):
        api.rings((), 1e-320)


def test_deadline_is_checked_inside_quadratic_pair_search(monkeypatch):
    clock = iter([0, 0, 0, 0, 2])
    monkeypatch.setattr(api.time, "monotonic", lambda: next(clock))
    with pytest.raises(TimeoutError):
        api.rings(((0, 0), (0, 0), (0, 0)), 1, deadline=1)


def test_empty_occurrence_paint_preserves_painter_without_drawing(scene):
    package, _pins, layer, *_others, canvas = scene
    layer.anchors = []
    painter = Mock()
    api.paint(painter, api.capture(canvas, package))
    painter.save.assert_not_called()
    painter.drawEllipse.assert_not_called()


def test_pythonqt_brush_boundary_receives_explicit_no_brush_value(scene):
    package, *_unused, canvas = scene
    painter = Mock()

    def native_set_brush(value):
        if not isinstance(value, QtGui.QBrush):
            raise TypeError("Called setBrush(QBrush brush) with wrong arguments")
        assert value.style() == QtCore.Qt.NoBrush, "Duplicate rings must stay unfilled"

    painter.setBrush.side_effect = native_set_brush
    api.paint(painter, api.capture(canvas, package))
    assert painter.setBrush.call_count == 2
    assert painter.save.call_count == painter.restore.call_count == 2


def test_real_qimage_contains_unfilled_red_and_yellow_ring_strokes(scene):
    package, _pins, _layer, _glyph, infos, block, canvas = scene
    infos[:] = infos[:1]
    infos[0].transform = QtGui.QTransform()
    block.transform = QtGui.QTransform()
    canvas.mapToViewportF = lambda p: QtCore.QPointF(p.x() + 30, p.y() + 20)
    image = QtGui.QImage(100, 100, QtGui.QImage.Format_ARGB32)
    image.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(image)
    try:
        api.paint(painter, api.capture(canvas, package))
    finally:
        painter.end()
    assert image.pixelColor(50, 50).alpha() == 0, "Ring center was filled"
    assert image.pixelColor(58, 50).green() > 150, "Yellow inner stroke missing"
    assert image.pixelColor(60, 50).red() > 150, "Red outer stroke missing"
    assert image.pixelColor(60, 50).green() < 50, "Outer stroke changed color"
