# this_file: tests/test_master_angles_gauge_qt.py
"""Verify actual Qt raster drawing and recorded native painter geometry."""

from math import atan2, degrees

import pytest
from legacy_panel_qt import QtCore, QtGui, QtWidgets, legacy_qt as legacy_qt


class ObservedPainter(QtGui.QPainter):
    """Observe geometry while forwarding every operation to the real Qt rasterizer."""

    def __init__(self, image):
        super().__init__(image)
        self.lines, self.labels = [], []

    def drawLine(self, a, b):
        self.lines.append((QtCore.QPointF(a), QtCore.QPointF(b), self.pen().widthF()))
        super().drawLine(a, b)

    def drawText(self, rect, flags, text):
        self.labels.append((QtCore.QRectF(rect), text))
        return super().drawText(rect, flags, text)


@pytest.fixture
def gauge(legacy_qt):
    widget = legacy_qt.modules["_master_angles_views"].Gauge()
    legacy_qt.owned.append(widget)
    return widget


@pytest.mark.parametrize(
    "angles", [[], [("Regular", 0)], [("Right", -45), ("Left", 45)]]
)
def test_gauge_when_drawn_then_real_pixels_baseline_labels_and_slant_match_angles(
    gauge, angles
):
    gauge.set_angles(angles)
    gauge.resize(600, 240)
    image = QtGui.QImage(600, 240, QtGui.QImage.Format_ARGB32)
    image.fill(QtCore.Qt.transparent)
    painter = ObservedPainter(image)
    try:
        gauge.draw(painter)
    finally:
        assert painter.end(), "Real QPainter must finish after every drawing path"
    assert image.pixelColor(0, 0) == gauge.palette.color(QtGui.QPalette.Base)
    assert [text for _rect, text in painter.labels] == [
        f"{name}  {angle:g}°" for name, angle in angles
    ]
    stems = [(a, b) for a, b, width in painter.lines if width == 3]
    assert len(stems) == len(angles), "Exactly one original colored stem per master"
    for (start, top), (_name, angle) in zip(stems, angles, strict=True):
        actual_angle = degrees(atan2(start.x() - top.x(), start.y() - top.y()))
        assert actual_angle == pytest.approx(angle), (
            "Negative angle leans right, measured from vertical"
        )
        assert top.y() < start.y() and 0 <= top.x() <= 600
        midpoint = (start + top) / 2
        assert image.pixelColor(
            round(midpoint.x()), round(midpoint.y())
        ) != gauge.palette.color(QtGui.QPalette.Base), (
            "A colored stem must reach the real raster image"
        )
    assert bool(painter.lines) is bool(angles), "Empty gauge paints only the background"


def test_gauge_when_stems_are_steep_then_geometry_stays_inside_its_own_master_slot(
    gauge,
):
    gauge.set_angles([("Right", -45), ("Left", 45)])
    gauge.resize(300, 400)
    image = QtGui.QImage(300, 400, QtGui.QImage.Format_ARGB32)
    painter = ObservedPainter(image)
    try:
        gauge.draw(painter)
    finally:
        painter.end()
    stems = [(a, b) for a, b, width in painter.lines if width == 3]
    assert stems[0][0] == QtCore.QPointF(75, 370)
    assert stems[0][1] == QtCore.QPointF(138, 307), (
        "Slot margin bounds the 45-degree height to63"
    )
    assert stems[1][0] == QtCore.QPointF(225, 370)
    assert stems[1][1].x() == pytest.approx(162)
    assert stems[1][1].y() == pytest.approx(307)


def test_gauge_when_master_labels_are_long_then_real_metrics_expand_scroll_width(gauge):
    name = "Very long master name " * 8
    gauge.set_angles([(name, -12.5), ("Black", 0)])
    metrics = QtGui.QFontMetrics(QtWidgets.QWidget.font(gauge))
    assert gauge.minimumWidth() >= 2 * (
        metrics.horizontalAdvance(f"{name}  -12.5°") + 24
    )
    gauge.set_angles([])
    assert gauge.minimumWidth() == 0 and gauge.angles == [], (
        "Invalidation releases oversized content"
    )


def test_gauge_when_paint_preflight_fails_then_real_paint_event_contains_and_reports(
    gauge,
):
    messages = []

    def stale():
        raise ValueError("owned source became stale")

    gauge.before_draw = stale
    gauge.report = messages.append
    gauge.resize(300, 200)
    gauge.grab()
    assert "owned source became stale" in gauge.paint_error
    assert messages and "Drawing failed" in messages[0]
    gauge.before_draw = None
    gauge.set_angles([("Regular", 0)])
    pixmap = gauge.grab()
    assert not pixmap.isNull() and gauge.paint_error == "", (
        "A new valid actual paint can recover"
    )
