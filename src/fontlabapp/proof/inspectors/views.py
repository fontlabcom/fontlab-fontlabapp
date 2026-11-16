# this_file: src/fontlabapp/proof/inspectors/views.py
# SPDX-License-Identifier: Apache-2.0
"""Complete spacing and contour-order painters on the shared safe paint boundary."""

from typing import Any

from fontlabapp.proof.inspect.views import ProofView, QtCore, QtGui
from fontlabapp.proof.inspectors.model import muted

MARGIN = 24


def outline_path(contours: Any) -> Any:
    """QPainterPath from contours given as [(x, y, on)] lists (cubic for two handles)."""
    from fontlab_pens.qt import QPainterPathPen, draw_onoff_contours

    pen = QPainterPathPen(path=QtGui.QPainterPath())
    # Contours with no on-curve point stay undrawn (pens would draw a TrueType loop).
    draw_onoff_contours([c for c in contours if any(p[2] for p in c)], pen)
    return pen.path


def fit_transform(rect: Any, width: Any, height: Any, margin: Any = 16) -> Any:
    """QTransform mapping font units in rect (y up) into a width × height widget (y down)."""
    if rect.width() <= 0 or rect.height() <= 0:
        return QtGui.QTransform()
    scale = min(
        (width - 2 * margin) / rect.width(),
        (height - 2 * margin) / rect.height(),
    )
    if scale <= 0:
        return QtGui.QTransform()
    dx = (width - rect.width() * scale) / 2 - rect.x() * scale
    dy = (height + rect.height() * scale) / 2 + rect.y() * scale
    return QtGui.QTransform(scale, 0, 0, -scale, dx, dy)


class Canvas(ProofView):
    """Original fitted spacing preview, boxes and both sidebearing labels."""

    def __init__(self, owner: Any) -> None:
        """Retain the original owner and None success diagnostic interface."""
        QtGui.QWidget.__init__(self)
        self.owner = owner
        self.paint_error = None
        self.before_draw = owner.draw_guard
        self.on_error = owner.paint_report
        self.setMinimumSize(560, 240)

    def paintEvent(self, event: Any) -> None:
        """Reuse painter finalization and preserve the original no-error None."""
        ProofView.paintEvent(self, event)
        if self.paint_error and self.owner is not None:
            try:
                self.owner.paint_cleanup()
            except Exception as error:  # noqa: BLE001 - contain native paint cleanup
                self.paint_error += "; cleanup: " + repr(error)
        if not self.paint_error:
            self.paint_error = None

    def draw(self, painter: Any) -> None:
        """Paint the complete original geometry, guides, labels and selectors."""
        owner = self.owner
        palette = self.palette
        painter.fillRect(self.rect, palette.color(QtGui.QPalette.Base))
        rows = owner.rows
        if not rows:
            painter.setPen(QtGui.QColor(muted(self)))
            painter.drawText(
                self.rect,
                int(QtCore.Qt.AlignCenter),
                owner.empty_message(),
            )
            return
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        total = rows[-1][1] + rows[-1][2]
        top, bottom = owner.ascender, owner.descender
        labels = 44 if owner.show_numbers.isChecked() else 8
        scale = min(
            (self.width - 2 * MARGIN) / max(total, 1),
            (self.height - 2 * MARGIN - labels) / max(top - bottom, 1),
        )
        left = (self.width - total * scale) / 2
        spare = self.height - 2 * MARGIN - labels - (top - bottom) * scale
        baseline = MARGIN + max(spare, 0) / 2 + top * scale
        guide = QtGui.QColor(palette.color(QtGui.QPalette.Mid))
        accent = QtGui.QColor(palette.color(QtGui.QPalette.Link))
        ink = QtGui.QColor(palette.color(QtGui.QPalette.WindowText))
        box = QtGui.QColor(guide)
        box.setAlpha(90)
        small = painter.font()
        small.setPointSizeF(max(small.pointSizeF() * 0.85, 8))
        painter.setFont(small)
        painter.setPen(QtGui.QPen(QtGui.QBrush(guide), 1.0))
        painter.drawLine(
            QtCore.QPointF(left, baseline),
            QtCore.QPointF(left + total * scale, baseline),
        )
        for name, x, advance, lsb, rsb in rows:
            x0 = left + x * scale
            if owner.show_boxes.isChecked():
                painter.setPen(QtGui.QPen(QtGui.QBrush(box), 1.0))
                painter.drawRect(
                    QtCore.QRectF(
                        x0,
                        baseline - top * scale,
                        advance * scale,
                        (top - bottom) * scale,
                    ),
                )
            painter.save()
            painter.translate(x0, baseline)
            painter.scale(scale, -scale)
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QBrush(ink))
            painter.drawPath(owner.path(name))
            painter.restore()
            if owner.show_numbers.isChecked() and lsb is not None:
                painter.setPen(accent)
                # LSB on the first row, RSB on the second, so neighbouring numbers never touch.
                y = baseline - bottom * scale + 6
                cell = QtCore.QRectF(x0 + 2, y, advance * scale - 4, 16)
                painter.drawText(
                    cell,
                    int(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop),
                    f"{round(lsb)}",
                )
                painter.drawText(
                    cell.translated(0, 17),
                    int(QtCore.Qt.AlignRight | QtCore.Qt.AlignTop),
                    f"{round(rsb)}",
                )


class OrderView(ProofView):
    """Complete original master columns, contour numbers, start dots and arrows."""

    def __init__(self, parent: Any = None) -> None:
        """Own only cached value geometry and safe paint callbacks."""
        QtGui.QWidget.__init__(self, parent)
        self.report, self._paint_error, self.paint_error = None, "", ""
        self.before_draw, self.on_error = None, self.report_error
        self.failure_cleanup = None
        self.setMinimumSize(560, 300)
        self.columns = []

    def paintEvent(self, event: Any) -> None:
        """Contain painter creation/draw/end failures and keep original error alias."""
        ProofView.paintEvent(self, event)
        if self.paint_error and self.failure_cleanup is not None:
            try:
                self.failure_cleanup()
            except Exception as error:  # noqa: BLE001 - contain native paint cleanup
                self.paint_error += "; cleanup: " + repr(error)
        self._paint_error = self.paint_error

    def report_error(self, text: str) -> None:
        """Report through the original owner hook without escaping into Qt."""
        self._paint_error = text
        if self.report is not None:
            self.report(f"Drawing failed: {text}")

    def draw(self, painter: Any) -> None:
        """Paint the complete original geometry, guides, labels and selectors."""
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        palette = self.palette
        painter.fillRect(self.rect, palette.color(QtGui.QPalette.Base))
        if not self.columns:
            return
        text_color = QtGui.QColor(
            palette.color(QtGui.QPalette.Active, QtGui.QPalette.WindowText),
        )  # copy: color() can alias the palette
        accent = QtGui.QColor(
            palette.color(QtGui.QPalette.Active, QtGui.QPalette.Link),
        )  # copy: color() can alias the palette
        union = QtCore.QRectF()
        for _, info in self.columns:
            union = union.united(outline_path([c[1] for c in info]).boundingRect())
        width = self.width / len(self.columns)
        label_font = QtGui.QFont(painter.font())
        label_font.setBold(True)
        for column, (master, info) in enumerate(self.columns):
            left = column * width
            painter.resetTransform()
            painter.setPen(text_color)
            painter.setFont(label_font)
            painter.drawText(
                QtCore.QRectF(left, 6, width, 20),
                int(QtCore.Qt.AlignHCenter),
                master,
            )
            fit = fit_transform(union, width, self.height - 28, 26)
            fit = QtGui.QTransform(
                fit.m11(),
                fit.m12(),
                fit.m21(),
                fit.m22(),
                fit.dx() + left,
                fit.dy() + 28,
            )
            ink = QtGui.QColor(text_color)
            ink.setAlpha(38)
            path = fit.map(outline_path([c[1] for c in info]))
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QBrush(ink))
            painter.drawPath(path)
            outline = QtGui.QPen(text_color)
            outline.setWidthF(1.0)
            painter.setPen(outline)
            painter.setBrush(QtGui.QBrush())
            painter.drawPath(path)
            for index, _points, start, nxt, _direction in info:
                p = fit.map(QtCore.QPointF(start[0], start[1]))
                q = fit.map(QtCore.QPointF(nxt[0], nxt[1]))
                self.arrow(painter, p, q, accent)
                painter.setPen(QtCore.Qt.NoPen)
                painter.setBrush(QtGui.QBrush(accent))
                painter.drawEllipse(p, 4.5, 4.5)
                painter.setPen(accent)
                painter.setFont(label_font)
                painter.drawText(
                    QtCore.QRectF(p.x() + 6, p.y() - 20, 40, 18),
                    0,
                    str(index + 1),
                )
            if column:
                divider = QtGui.QColor(text_color)
                divider.setAlpha(40)
                painter.setPen(divider)
                painter.drawLine(
                    QtCore.QPointF(left, 8),
                    QtCore.QPointF(left, self.height - 8),
                )

    def arrow(self, painter: Any, p: Any, q: Any, color: Any) -> None:
        """Draw the original first-segment direction arrow in widget coordinates."""
        dx, dy = q.x() - p.x(), q.y() - p.y()
        length = (dx * dx + dy * dy) ** 0.5
        if length < 1:
            return
        ux, uy = dx / length, dy / length
        tip = QtCore.QPointF(p.x() + ux * 22, p.y() + uy * 22)
        pen = QtGui.QPen(color)
        pen.setWidthF(2.0)
        painter.setPen(pen)
        painter.drawLine(p, tip)
        head = QtGui.QPolygonF()
        head.append(tip)
        head.append(
            QtCore.QPointF(tip.x() - ux * 8 - uy * 5, tip.y() - uy * 8 + ux * 5),
        )
        head.append(
            QtCore.QPointF(tip.x() - ux * 8 + uy * 5, tip.y() - uy * 8 - ux * 5),
        )
        painter.setBrush(QtGui.QBrush(color))
        painter.drawPolygon(head)
