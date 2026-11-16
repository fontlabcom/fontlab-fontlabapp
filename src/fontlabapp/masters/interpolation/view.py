# this_file: src/fontlabapp/masters/interpolation/view.py
# SPDX-License-Identifier: Apache-2.0
"""Complete original interpolation painter on the verified owned paint boundary."""

from typing import Any

from fontlabapp.anchors.inspect.views import AnchorView, QtCore, QtGui
from fontlabapp.masters.interpolation.model import fit_transform, outline_path


class BlendView(AnchorView):
    """Keep every original outline and report interface with safe painter cleanup."""

    def __init__(self, parent: Any = None) -> None:
        """Own all plain endpoint/mix values and the optional legacy report hook."""
        super().__init__(parent)
        self.a, self.b, self.mix, self.message = [], [], [], ""
        self.report = None

    @property
    def _paint_error(self) -> str:
        """Expose the original empty-string success diagnostic alongside error=None."""
        return self.paint_error or ""

    def paint(self, painter: Any) -> None:
        """Draw both full endpoint paths, the mixed outline and every on-curve node."""
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        palette = self.palette
        painter.fillRect(self.rect, palette.color(QtGui.QPalette.Base))
        text = QtGui.QColor(
            palette.color(QtGui.QPalette.Active, QtGui.QPalette.WindowText)
        )
        if self.message:
            painter.setPen(text)
            painter.drawText(
                self.rect,
                int(QtCore.Qt.AlignCenter | QtCore.Qt.TextWordWrap),
                self.message,
            )
        path_a, path_b = (outline_path(self.a), outline_path(self.b))
        rect = path_a.boundingRect().united(path_b.boundingRect())
        painter.setTransform(fit_transform(rect, self.width, self.height, 24))
        faint = QtGui.QColor(text)
        faint.setAlpha(70)
        pen = QtGui.QPen(faint)
        pen.setCosmetic(True)
        pen.setStyle(QtCore.Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(QtGui.QBrush())
        painter.drawPath(path_a)
        painter.drawPath(path_b)
        if self.mix:
            accent = QtGui.QColor(
                palette.color(QtGui.QPalette.Active, QtGui.QPalette.Link)
            )
            fill = QtGui.QColor(text)
            fill.setAlpha(200)
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QBrush(fill))
            painter.drawPath(outline_path(self.mix))
            dot = QtGui.QPen(accent)
            dot.setCosmetic(True)
            dot.setWidthF(4)
            dot.setCapStyle(QtCore.Qt.RoundCap)
            painter.setPen(dot)
            for contour in self.mix:
                for x, y, on in contour:
                    if on:
                        painter.drawPoint(QtCore.QPointF(x, y))
