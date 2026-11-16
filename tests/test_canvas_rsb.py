# this_file: tests/test_canvas_rsb.py
"""Independent RSB geometry, placed-item reads and borrowed-painter controls."""

import importlib
import math
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from PySide6 import QtCore, QtGui

api = importlib.import_module("fontlabapp.metrics.canvas_rsb.model")


@pytest.mark.parametrize("direction,x", [(0, 600), (2, 0)])
def test_upright_line_and_triangle_keep_original_geometry(direction, x):
    line, triangle, stroke = api.geometry(600, 800, -200, 500, 0, 1, direction)
    assert line == ((x, 800), (x, -200)), "Wrong direction edge"
    assert triangle == ((290, -200), (300, -190), (310, -200))
    assert stroke == 1


@pytest.mark.parametrize("width", [0, -300, 600])
def test_italic_geometry_preserves_negative_width_and_scale_exponents(width):
    line, triangle, stroke = api.geometry(width, 800, -200, 500, 10, 2, 0)
    k = math.tan(math.radians(10))
    assert line[0] == pytest.approx((width + k * 550, 800))
    assert line[1] == pytest.approx((width + k * -450, -200))
    assert triangle[0] == pytest.approx((width / 2 - 5 - k * 450, -200))
    assert triangle[1] == pytest.approx((width / 2 - k * 445, -195))
    assert triangle[2] == pytest.approx((width / 2 + 5 - k * 450, -200))
    assert stroke == pytest.approx(2**-0.9)


@pytest.mark.parametrize(
    "field,value", [(0, math.nan), (1, math.inf), (4, 90), (5, 0), (5, -1), (6, 1)]
)
def test_invalid_geometry_is_refused(field, value):
    args = [600, 800, -200, 500, 0, 1, 0]
    args[field] = value
    with pytest.raises(ValueError):
        api.geometry(*args)


@pytest.fixture
def scene(monkeypatch):
    native = NS(
        FontMetrics=lambda package, master: NS(
            ascender=800, descender=-200, xHeight=500
        )
    )
    monkeypatch.setattr(
        api,
        "_native",
        lambda name: native if name == "fontlab" else NS(QtCore=QtCore, QtGui=QtGui),
    )
    package = NS(id=7, master="Regular", masters=["Regular"], italicAngle_value=0)
    glyph = NS(
        id=31,
        name="H",
        isNull=False,
        findLayer=lambda master: NS(isNull=False, advanceWidth=600),
    )
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
        textBlocks=lambda: [block],
        mapToViewportF=lambda p: QtCore.QPointF(3 * p.x() + 7, -3 * p.y() + 11),
    )
    return package, infos, block, canvas


def test_each_repeated_item_uses_glyph_block_canvas_maps_without_extra_kerning(scene):
    package, _infos, _block, canvas = scene
    records = api.capture(canvas, package, 0)
    assert len(records) == 2 and records[0].item != records[1].item
    assert [r.active for r in records] == [True, False]
    a = api.map_point(records[0].transform, records[0].line[0])
    b = api.map_point(records[1].transform, records[1].line[0])
    assert a == (4147, -5689), "Wrong glyph × block × canvas composition"
    assert b[0] - a[0] == 575 * 6, "Glyph transform already includes kerning"
    assert records[0].stroke == pytest.approx(6**-0.9)
    assert records[0].master == "Regular"


@pytest.mark.parametrize("native_angle", [-10, 10])
@pytest.mark.parametrize("direction,edge", [(0, 600), (2, 0)])
def test_capture_converts_fontlab_italic_angle_to_original_glyphs_convention(
    scene, native_angle, direction, edge
):
    package, _infos, _block, canvas = scene
    package.italicAngle_value = native_angle
    record = api.capture(canvas, package, direction)[0]
    slope = -math.tan(math.radians(native_angle))
    assert record.line[0] == pytest.approx((edge + slope * 550, 800))
    assert record.line[1] == pytest.approx((edge - slope * 450, -200))


def test_capture_empty_foreign_missing_and_expired_sources(scene):
    package, infos, block, canvas = scene
    block.package = NS(id=99)
    assert api.capture(canvas, package, 0) == ()
    block.package = package
    block.getAllGlyphs = lambda: None
    assert api.capture(canvas, package, 0) == ()
    block.getAllGlyphs = lambda: infos
    infos[0].glyph.findLayer = lambda master: None
    with pytest.raises(ValueError, match="layer"):
        api.capture(canvas, package, 0)
    with pytest.raises(TimeoutError):
        api.capture(canvas, package, 0, deadline=0)


def test_capture_rejects_changes_and_nonfinite_transforms(scene):
    package, infos, block, canvas = scene

    def mutate():
        package.master = "Bold"
        return [block]

    canvas.textBlocks = mutate
    with pytest.raises(ValueError, match="Master"):
        api.capture(canvas, package, 0)
    package.master = "Regular"
    canvas.textBlocks = lambda: [block]
    infos[0].transform = QtGui.QTransform(0, 0, 0, 0, 0, 0)
    with pytest.raises(ValueError, match="scale"):
        api.capture(canvas, package, 0)


def test_paint_restores_borrowed_painter_without_ending_it(scene):
    package, _, _, canvas = scene
    painter = Mock()
    records = api.capture(canvas, package, 0)
    api.paint(painter, records, "#3366aa")
    assert painter.drawLine.call_count == 2 and painter.drawPolygon.call_count == 2
    assert painter.save.call_count == painter.restore.call_count == 2
    painter.end.assert_not_called()
    painter.drawLine.side_effect = ValueError("injected")
    with pytest.raises(ValueError, match="injected"):
        api.paint(painter, records, "#3366aa")
    assert painter.save.call_count == painter.restore.call_count


def test_rendered_primitives_have_visible_pixels_on_owned_qimage(scene):
    package, infos, block, canvas = scene
    infos[:] = infos[:1]
    infos[0].transform = QtGui.QTransform()
    block.transform = QtGui.QTransform()
    canvas.mapToViewportF = lambda p: QtCore.QPointF(
        0.1 * p.x() + 10, -0.1 * p.y() + 85
    )
    image = QtGui.QImage(100, 120, QtGui.QImage.Format_ARGB32)
    image.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(image)
    try:
        api.paint(painter, api.capture(canvas, package, 0), "#3366aa")
    finally:
        painter.end()
    assert image.pixelColor(70, 20).alpha() > 0, "Expected mapped RSB line absent"
    assert image.pixelColor(40, 102).alpha() > 0, "Expected triangle absent"


def test_lazy_public_facade_preserves_host_free_imports():
    scripting = importlib.import_module("fontlabapp.core.scripting")
    assert scripting.canvas_rsb_api() is api


def test_snapshot_contains_native_occurrence_and_font_identities(scene):
    package, infos, block, canvas = scene
    records = api.capture(canvas, package, 0)
    assert records[0].item == (block.id, infos[0].id)
    assert records[0].package_id == package.id and records[0].glyph_id == 31
    infos[0].id = 99
    assert api.capture(canvas, package, 0) != records
    assert records[0].item == (51, 41), "Published snapshot changed with its source"


def test_nonfinite_viewport_refuses_even_without_matching_glyphs(scene):
    package, _infos, block, canvas = scene
    block.package = NS(id=99)
    canvas.mapToViewportF = lambda p: QtCore.QPointF(math.nan, 0)
    with pytest.raises(ValueError, match="viewport"):
        api.capture(canvas, package, 0)
