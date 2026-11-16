# this_file: src/fontlabapp/guides/inspect/views.py
# SPDX-License-Identifier: Apache-2.0
"""Original guide-grid rendering on the existing safe native paint boundary."""

from typing import Any

from fontlabapp.components.inspect.views import BadgeGrid
from fontlabapp.proof.inspect.views import ProofView, QtCore, QtGui


class GridPreview(ProofView):
    """Custom painter: the first glyph's outline with the planned grid lines on top."""

    paintEvent = BadgeGrid.paintEvent

    def __init__(self, parent: Any = None) -> None:
        QtGui.QWidget.__init__(self, parent)
        self.before_draw = None
        self.error = None
        self.failure_cleanup = None
        self.setMinimumHeight(200)
        self.paint_error = ""
        self.on_error = None
        (self.path, self.advance, self.records, self.frame) = (
            None,
            0,
            [],
            (-250.0, 750.0),
        )

    def set_content(self, path: Any, advance: Any, records: Any, frame: Any) -> None:
        """Retain the original complete guide preview behind the shared paint boundary."""
        (self.path, self.advance, self.records, self.frame) = (
            path,
            advance,
            records,
            frame,
        )
        self.update()

    def draw(self, painter: Any) -> None:
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        ink = QtGui.QColor(self.palette.color(QtGui.QPalette.WindowText))
        faint = QtGui.QColor(ink)
        faint.setAlpha(40)
        glyph_ink = QtGui.QColor(ink)
        glyph_ink.setAlpha(170)
        accent = QtGui.QColor(self.palette.color(QtGui.QPalette.Link))
        (width, height) = (float(self.width), float(self.height))
        painter.setPen(QtGui.QPen(QtGui.QBrush(faint), 1.0))
        painter.drawRoundedRect(QtCore.QRectF(0.5, 0.5, width - 1, height - 1), 8, 8)
        (bottom, top) = self.frame
        (left, right) = (0.0, float(max(self.advance, 1)))
        for x, y, angle, _ in self.records:
            if angle == 0:
                (bottom, top) = (min(bottom, y), max(top, y))
            else:
                (left, right) = (min(left, x), max(right, x))
        scale = min(
            (width - 40) / max(1.0, right - left),
            (height - 30) / max(1.0, top - bottom),
        )
        ox = (width - (right - left) * scale) / 2.0 - left * scale
        oy = 15 + top * scale

        def to_view(x, y):
            return QtCore.QPointF(ox + x * scale, oy - y * scale)

        painter.setPen(QtGui.QPen(QtGui.QBrush(faint), 1.0))
        painter.drawLine(to_view(left, 0), to_view(right, 0))
        if self.path is not None:
            painter.save()
            painter.translate(ox, oy)
            painter.scale(scale, 0 - scale)
            painter.fillPath(self.path, QtGui.QBrush(glyph_ink))
            painter.restore()
        painter.setPen(QtGui.QPen(QtGui.QBrush(accent), 1.0))
        for x, y, angle, _ in self.records:
            if angle == 0:
                painter.drawLine(
                    QtCore.QPointF(8, oy - y * scale),
                    QtCore.QPointF(width - 8, oy - y * scale),
                )
            else:
                painter.drawLine(
                    QtCore.QPointF(ox + x * scale, 8),
                    QtCore.QPointF(ox + x * scale, height - 8),
                )
