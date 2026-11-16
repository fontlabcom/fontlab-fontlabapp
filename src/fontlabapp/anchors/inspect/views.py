# this_file: src/fontlabapp/anchors/inspect/views.py
# SPDX-License-Identifier: Apache-2.0
"""Original full anchor diagrams on the native-verified None-error paint boundary."""

from typing import Any

from fontlabapp.components.inspect.views import BadgeGrid
from fontlabapp.proof.inspect.views import ProofView, QtCore, QtGui
from fontlabapp.anchors.inspect.model import pen


class AnchorView(ProofView):
    """Reuse the safe painter adapter, with panels instead of component cards."""

    minimum_height = 300
    paintEvent = BadgeGrid.paintEvent
    draw = BadgeGrid.draw

    def __init__(self, parent: Any = None) -> None:
        """Own all callbacks and the original exact None success sentinel."""
        QtGui.QWidget.__init__(self, parent)
        self.panels = []
        self.error = self.paint_error = None
        self.before_draw = self.on_error = self.failure_cleanup = None
        self.setMinimumHeight(self.minimum_height)

    def set_panels(self, panels: Any) -> None:
        """Replace complete plain panel data and request one paint."""
        self.panels = panels
        self.update()


class CloudView(AnchorView):
    """One panel per master: faint overlaid outlines, anchor dots, extremes underneath."""

    minimum_height = 320

    def paint(self, painter: Any) -> None:
        """Retain the original paint behavior and complete native interface."""
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        text = QtGui.QColor(self.palette.color(QtGui.QPalette.WindowText))
        accent = QtGui.QColor(self.palette.color(QtGui.QPalette.Link))
        ghost = QtGui.QColor(text)
        ghost.setAlpha(28)
        faint = QtGui.QColor(text)
        faint.setAlpha(110)
        area = QtCore.QRectF(0, 0, self.width, self.height)
        if not self.panels:
            painter.setPen(pen(faint))
            painter.drawText(
                area, int(QtCore.Qt.AlignCenter), "Select glyphs with anchors"
            )
            return
        bounds = QtCore.QRectF()
        for _, paths, points in self.panels:
            for path in paths:
                bounds = bounds.united(path.boundingRect())
            for _, x, y in points:
                bounds = bounds.united(QtCore.QRectF(x - 1, y - 1, 2, 2))
        width = area.width() / len(self.panels)
        line = QtGui.QFontMetrics(painter.font()).height()
        (top, bottom) = (line + 14, 2 * line + 14)
        scale = min(
            (width - 28) / max(bounds.width(), 1),
            (area.height() - top - bottom) / max(bounds.height(), 1),
        )
        for index, (master, paths, points) in enumerate(self.panels):
            left = index * width
            painter.setPen(pen(text))
            painter.drawText(
                QtCore.QRectF(left, 2, width, line + 4),
                int(QtCore.Qt.AlignHCenter),
                master,
            )
            ox = left + (width - bounds.width() * scale) / 2 - bounds.x() * scale
            oy = top + bounds.bottom() * scale
            painter.save()
            painter.translate(ox, oy)
            painter.scale(scale, -scale)
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QBrush(ghost))
            for path in paths:
                painter.drawPath(path)
            painter.setPen(pen(faint, 0))
            painter.drawLine(QtCore.QLineF(bounds.x(), 0, bounds.right(), 0))
            painter.restore()
            painter.setPen(pen(accent, 1.2))
            painter.setBrush(QtGui.QBrush(accent))
            for _, x, y in points:
                painter.drawEllipse(
                    QtCore.QPointF(ox + x * scale, oy - y * scale), 3, 3
                )
            if points:
                (xs, ys) = ([p[1] for p in points], [p[2] for p in points])
                note = f"{len(points)} anchors\nx {min(xs)}…{max(xs)}   y {min(ys)}…{max(ys)}"
            else:
                note = "no anchors of this name"
            painter.setPen(pen(faint))
            painter.drawText(
                QtCore.QRectF(left, area.height() - bottom + 6, width, bottom),
                int(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop),
                note,
            )


class AttachmentView(AnchorView):
    """One panel per master: base outline, attached mark in the accent colour, the two anchors."""

    minimum_height = 300

    def paint(self, painter: Any) -> None:
        """Retain the original paint behavior and complete native interface."""
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        text = QtGui.QColor(self.palette.color(QtGui.QPalette.WindowText))
        accent = QtGui.QColor(self.palette.color(QtGui.QPalette.Link))
        faint = QtGui.QColor(text)
        faint.setAlpha(60)
        muted = QtGui.QColor(text)
        muted.setAlpha(170)
        area = QtCore.QRectF(0, 0, self.width, self.height)
        if not self.panels:
            painter.setPen(pen(text))
            painter.drawText(
                area, int(QtCore.Qt.AlignCenter), "No base / mark pair to show"
            )
            return
        boxes = QtCore.QRectF()
        for _, base, mark, _, advance, _ in self.panels:
            boxes = boxes.united(base.boundingRect()).united(
                QtCore.QRectF(0, 0, advance, 1)
            )
            if mark is not None:
                boxes = boxes.united(mark.boundingRect())
        width = area.width() / len(self.panels)
        line = QtGui.QFontMetrics(painter.font()).height()
        (top, bottom) = (line + 16, line + 14)
        scale = min(
            (width - 32) / max(boxes.width(), 1),
            (area.height() - top - bottom) / max(boxes.height(), 1),
        )
        for index, (master, base, mark, point, advance, note) in enumerate(self.panels):
            left = index * width
            painter.setPen(pen(text))
            painter.drawText(
                QtCore.QRectF(left, 4, width, line + 4),
                int(QtCore.Qt.AlignHCenter),
                master,
            )
            painter.setPen(pen(muted))
            painter.drawText(
                QtCore.QRectF(left, area.height() - line - 4, width, line + 4),
                int(QtCore.Qt.AlignHCenter),
                note,
            )
            ox = left + (width - boxes.width() * scale) / 2 - boxes.x() * scale
            oy = top + boxes.bottom() * scale
            painter.save()
            painter.translate(ox, oy)
            painter.scale(scale, -scale)
            painter.setPen(pen(faint, 0))
            painter.drawLine(QtCore.QLineF(boxes.x(), 0, boxes.right(), 0))
            painter.drawLine(QtCore.QLineF(advance, boxes.y(), advance, boxes.bottom()))
            painter.drawLine(QtCore.QLineF(0, boxes.y(), 0, boxes.bottom()))
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QBrush(text))
            painter.drawPath(base)
            if mark is not None:
                painter.setBrush(QtGui.QBrush(accent))
                painter.drawPath(mark)
            painter.restore()
            if point is not None:
                painter.setPen(pen(accent, 1.5))
                painter.setBrush(
                    QtGui.QBrush(QtGui.QColor(self.palette.color(QtGui.QPalette.Base)))
                )
                painter.drawEllipse(
                    QtCore.QPointF(ox + point[0] * scale, oy - point[1] * scale), 4, 4
                )
