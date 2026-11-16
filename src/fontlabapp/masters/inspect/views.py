# this_file: src/fontlabapp/masters/inspect/views.py
# SPDX-License-Identifier: Apache-2.0
"""Original native width lines and grouped ink-area bars, with shared paint containment."""

import itertools
from typing import Any

from fontlabapp.proof.inspect.views import ProofView, QtCore, QtGui
from fontlabapp.masters.inspect.model import label_tops, nice_ticks, spread


def series_colors(widget: Any, count: Any) -> Any:
    """Count distinguishable colours derived from the palette accent (hue steps of the golden angle)."""
    base = QtGui.QColor(
        widget.palette.color(QtGui.QPalette.Active, QtGui.QPalette.Link)
    )
    hue = max(base.hsvHue(), 0)
    colors = []
    for i in range(count):
        color = QtGui.QColor()
        color.setHsv(
            int(hue + i * 137.5) % 360,
            max(base.hsvSaturation(), 150),
            min(max(base.value(), 170), 220),
        )
        colors.append(color)
    return colors


class Chart(ProofView):
    """Reuse the tested paint boundary while retaining original report/error names."""

    def paintEvent(self, event: Any) -> None:
        """End the native painter even if drawing, finalization or reporting fails."""
        ProofView.paintEvent(self, event)
        self._paint_error = self.paint_error

    def report_error(self, text: str) -> None:
        """Preserve the original report callback for the owning visible dialog."""
        self._paint_error = text
        if self.report is not None:
            self.report(f"Drawing failed: {text}")


class LineChart(Chart):
    """Masters on x, advance width on y, one coloured line per glyph."""

    def __init__(self, parent: Any = None) -> None:
        """Draw the original chart labels, axes and complete data series."""
        QtGui.QWidget.__init__(self, parent)
        self.report, self._paint_error = None, ""
        self.before_draw, self.on_error = None, self.report_error
        self.paint_error = ""
        self.setMinimumSize(520, 300)
        (self.masters, self.series) = ([], [])

    def draw(self, painter: Any) -> None:
        """Draw the original chart labels, axes and complete data series."""
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        palette = self.palette
        painter.fillRect(self.rect, palette.color(QtGui.QPalette.Base))
        values = [v for (_, row) in self.series for v in row if v is not None]
        if not values or not self.masters:
            return
        text = QtGui.QColor(
            palette.color(QtGui.QPalette.Active, QtGui.QPalette.WindowText)
        )
        faint = QtGui.QColor(text)
        faint.setAlpha(40)
        ticks = nice_ticks(min(values), max(values))
        (low, high) = (ticks[0], ticks[-1] if ticks[-1] > ticks[0] else ticks[0] + 1)
        (left, right, top, bottom) = (56, self.width - 110, 18, self.height - 34)
        step = (right - left) / max(len(self.masters) - 1, 1)

        def x_of(i: Any) -> Any:
            """Draw the original chart labels, axes and complete data series."""
            return left + i * step if len(self.masters) > 1 else (left + right) / 2

        def y_of(v: Any) -> Any:
            """Draw the original chart labels, axes and complete data series."""
            return bottom - (v - low) / (high - low) * (bottom - top)

        small = QtGui.QFont(painter.font())
        small.setPointSizeF(small.pointSizeF() * 0.85)
        painter.setFont(small)
        for tick in ticks:
            y = y_of(tick)
            painter.setPen(faint)
            painter.drawLine(QtCore.QPointF(left, y), QtCore.QPointF(right, y))
            painter.setPen(text)
            painter.drawText(
                QtCore.QRectF(0, y - 8, left - 8, 16),
                int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter),
                f"{tick:g}",
            )
        for i, master in enumerate(self.masters):
            painter.setPen(text)
            painter.drawText(
                QtCore.QRectF(x_of(i) - 60, bottom + 8, 120, 18),
                int(QtCore.Qt.AlignHCenter),
                master,
            )
        colors = series_colors(self, len(self.series))
        rows = [
            [
                None if v is None else (QtCore.QPointF(x_of(i), y_of(v)), v)
                for (i, v) in enumerate(row)
            ]
            for (_, row) in self.series
        ]
        tops = {}
        for column in range(len(self.masters)):
            present = sorted(
                (row[column][0].y(), k)
                for (k, row) in enumerate(rows)
                if row[column] is not None
            )
            for (_, k), y in zip(
                present, label_tops([y for (y, _) in present], 16), strict=False
            ):
                tops[k, column] = y
        ends = [
            (row_points[-1][0].y() - 8, k)
            for (k, row_points) in enumerate(
                [[p for p in row if p is not None] for row in rows]
            )
            if row_points
        ]
        end_tops = {
            k: y
            for ((_, k), y) in zip(
                sorted(ends), spread([y for (y, _) in sorted(ends)], 16), strict=False
            )
        }
        label = QtGui.QFont(small)
        label.setBold(True)
        for k, ((name, _), color) in enumerate(zip(self.series, colors, strict=False)):
            pen = QtGui.QPen(color)
            pen.setWidthF(2.2)
            painter.setPen(pen)
            points = [p for p in rows[k] if p is not None]
            for (a, _), (b, _) in itertools.pairwise(points):
                painter.drawLine(a, b)
            painter.setBrush(QtGui.QBrush(color))
            for column, entry in enumerate(rows[k]):
                if entry is None:
                    continue
                (point, v) = entry
                painter.drawEllipse(point, 3.5, 3.5)
                painter.drawText(
                    QtCore.QRectF(point.x() - 30, tops[k, column], 60, 16),
                    int(QtCore.Qt.AlignHCenter),
                    f"{v:g}",
                )
            if k in end_tops:
                painter.setFont(label)
                painter.drawText(
                    QtCore.QRectF(right + 34, end_tops[k], 76, 16),
                    int(QtCore.Qt.AlignVCenter),
                    name,
                )
                painter.setFont(small)


class BarChart(Chart):
    """Groups of bars: one group per glyph, one bar per master, shared y scale."""

    def __init__(self, parent: Any = None) -> None:
        """Draw the original chart labels, axes and complete data series."""
        QtGui.QWidget.__init__(self, parent)
        self.report, self._paint_error = None, ""
        self.before_draw, self.on_error = None, self.report_error
        self.paint_error = ""
        self.setMinimumSize(560, 300)
        (self.masters, self.groups) = ([], [])

    def draw(self, painter: Any) -> None:
        """Draw the original chart labels, axes and complete data series."""
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        palette = self.palette
        painter.fillRect(self.rect, palette.color(QtGui.QPalette.Base))
        values = [v for (_, row) in self.groups for v in row]
        if not values:
            return
        text = QtGui.QColor(
            palette.color(QtGui.QPalette.Active, QtGui.QPalette.WindowText)
        )
        faint = QtGui.QColor(text)
        faint.setAlpha(40)
        ticks = nice_ticks(0, max(values))
        high = ticks[-1] or 1
        (left, right, top, bottom) = (56, self.width - 12, 34, self.height - 30)
        small = QtGui.QFont(painter.font())
        small.setPointSizeF(small.pointSizeF() * 0.85)
        painter.setFont(small)
        for tick in ticks:
            y = bottom - tick / high * (bottom - top)
            painter.setPen(faint)
            painter.drawLine(QtCore.QPointF(left, y), QtCore.QPointF(right, y))
            painter.setPen(text)
            painter.drawText(
                QtCore.QRectF(0, y - 8, left - 8, 16),
                int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter),
                f"{tick / 1000:g}k",
            )
        colors = series_colors(self, len(self.masters))
        x = left + 4
        for _i, (master, color) in enumerate(zip(self.masters, colors, strict=False)):
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QBrush(color))
            painter.drawRoundedRect(QtCore.QRectF(x, 10, 10, 10), 2, 2)
            painter.setPen(text)
            painter.drawText(
                QtCore.QRectF(x + 14, 6, 120, 18), int(QtCore.Qt.AlignVCenter), master
            )
            x += (
                24
                + painter.boundingRect(QtCore.QRectF(0, 0, 400, 20), 0, master).width()
            )
        group = (right - left) / len(self.groups)
        bar = min(28, group * 0.8 / max(len(self.masters), 1))
        for g, (name, row) in enumerate(self.groups):
            start = left + g * group + (group - bar * len(row)) / 2
            for m, (value, color) in enumerate(zip(row, colors, strict=False)):
                height = value / high * (bottom - top)
                rect = QtCore.QRectF(
                    start + m * bar + 1, bottom - height, bar - 2, height
                )
                painter.setPen(QtCore.Qt.NoPen)
                painter.setBrush(QtGui.QBrush(color))
                painter.drawRoundedRect(rect, 2, 2)
            painter.setPen(text)
            painter.drawText(
                QtCore.QRectF(left + g * group, bottom + 6, group, 18),
                int(QtCore.Qt.AlignHCenter),
                name,
            )
