# this_file: src/fontlabapp/masters/angles/views.py
# SPDX-License-Identifier: Apache-2.0
"""Original per-master slanted stems on the shared contained painter boundary."""

from math import radians, tan
from typing import Any

from fontlabapp.masters.inspect.views import Chart, QtCore, QtGui, series_colors


class Gauge(Chart):
    """A baseline and labelled angle stem for each ordered master."""

    def __init__(self, parent: Any = None) -> None:
        """Retain native controls only; the dialog supplies immutable angle values."""
        QtGui.QWidget.__init__(self, parent)
        self.report, self._paint_error = None, ""
        self.before_draw, self.on_error = None, self.report_error
        self.paint_error = ""
        self.masters, self.angles = [], []
        self.setMinimumHeight(170)

    def set_angles(self, angles: list[tuple[str, float]]) -> None:
        """Keep every full master label readable in the owned horizontal viewport."""
        self.angles = angles
        metrics = QtGui.QFontMetrics(self.font)
        widths = [
            metrics.width(f"{master}  {angle:g}°") + 24
            for master, angle in angles
        ]
        self.setMinimumWidth(len(angles) * max([150, *widths]))
        self.update()

    def draw(self, painter: Any) -> None:
        """Negative angles lean right; contain ±45-degree stems within each slot."""
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        palette = self.palette
        painter.fillRect(self.rect, palette.color(QtGui.QPalette.Base))
        if not self.angles:
            return
        text = QtGui.QColor(
            palette.color(QtGui.QPalette.Active, QtGui.QPalette.WindowText)
        )
        faint = QtGui.QColor(text)
        faint.setAlpha(60)
        base_y = self.height - 30
        slot = self.width / len(self.angles)
        slope = max(abs(tan(radians(angle))) for _, angle in self.angles)
        height = self.height - 64
        if slope:
            height = min(height, max(1, slot / 2 - 12) / slope)
        painter.setPen(faint)
        painter.drawLine(
            QtCore.QPointF(12, base_y), QtCore.QPointF(self.width - 12, base_y)
        )
        for index, ((master, angle), color) in enumerate(
            zip(self.angles, series_colors(self, len(self.angles)), strict=True)
        ):
            x = slot * (index + 0.5)
            painter.setPen(faint)
            painter.drawLine(
                QtCore.QPointF(x, base_y), QtCore.QPointF(x, base_y - height)
            )
            top = QtCore.QPointF(x - tan(radians(angle)) * height, base_y - height)
            pen = QtGui.QPen(color)
            pen.setWidthF(3)
            pen.setCapStyle(QtCore.Qt.RoundCap)
            painter.setPen(pen)
            painter.drawLine(QtCore.QPointF(x, base_y), top)
            painter.setPen(text)
            painter.drawText(
                QtCore.QRectF(x - slot / 2, base_y + 6, slot, 18),
                int(QtCore.Qt.AlignHCenter),
                f"{master}  {angle:g}°",
            )
