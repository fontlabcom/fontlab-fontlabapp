# this_file: src/fontlabapp/components/inspect/views.py
# SPDX-License-Identifier: Apache-2.0
"""Complete original card painter with guarded source reads and owned cleanup."""

from typing import Any

from fontlabapp.proof.inspect.views import ProofView, QtCore, QtGui
from fontlabapp.components.inspect.model import pen

CARD_W, DRAW_H, LINE_H, PAD = 212, 92, 20, 10
COLUMNS = 3


class BadgeGrid(ProofView):
    """Cards laid out in rows that fit the widget width; height follows the number of rows."""

    def __init__(self, parent: Any = None) -> None:
        """Preserve the original   init   calculation and native interface."""
        QtGui.QWidget.__init__(self, parent)
        self.cards = []
        self.error = None
        self.paint_error = None
        self.failure_cleanup = None
        self.before_draw = None
        self.on_error = None
        self.columns = 1

    def set_cards(self, cards: Any, width: Any) -> None:
        """Preserve the original set cards calculation and native interface."""
        self.cards = cards
        self.relayout(width)
        self.update()

    def card_height(self) -> Any:
        """Preserve the original card height calculation and native interface."""
        lines = max((len(c[3]) for c in self.cards), default=0)
        return DRAW_H + LINE_H + lines * LINE_H + 2 * PAD

    def relayout(self, width: Any) -> None:
        """Preserve the original relayout calculation and native interface."""
        columns = max(1, int((width - 4) // (CARD_W + 8)))
        rows = (len(self.cards) + columns - 1) // columns
        self.setFixedHeight(max(1, rows) * (self.card_height() + 8) + 4)
        self.columns = columns

    def resizeEvent(self, event: Any) -> None:
        """Preserve the original resizeEvent calculation and native interface."""
        QtGui.QWidget.resizeEvent(self, event)
        if self.cards:
            self.relayout(self.width)

    def paintEvent(self, event: Any) -> None:
        """Reuse native activation/finalization guards and the original None sentinel."""
        ProofView.paintEvent(self, event)
        if self.paint_error and self.failure_cleanup is not None:
            try:
                self.failure_cleanup(self.paint_error)
            except Exception as error:  # noqa: BLE001 - contain native paint cleanup
                self.paint_error += "; cleanup: " + repr(error)
        self.error = self.paint_error or None

    def draw(self, painter: Any) -> None:
        """Keep the original complete paint method behind the shared safe boundary."""
        self.paint(painter)

    def badge(
        self, painter: Any, x: Any, y: Any, text: Any, fill: Any, ink: Any
    ) -> Any:
        """Preserve the original badge calculation and native interface."""
        metrics = QtGui.QFontMetrics(painter.font())
        width = metrics.width(text) + 12
        rect = QtCore.QRectF(x, y + 2, width, LINE_H - 4)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QBrush(fill))
        painter.drawRoundedRect(rect, 7, 7)
        painter.setPen(pen(ink))
        painter.drawText(rect, int(QtCore.Qt.AlignCenter), text)
        return width

    def paint(self, painter: Any) -> None:
        """Preserve the original paint calculation and native interface."""
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        text = QtGui.QColor(self.palette.color(QtGui.QPalette.WindowText))
        base = QtGui.QColor(self.palette.color(QtGui.QPalette.Base))
        accent = QtGui.QColor(self.palette.color(QtGui.QPalette.Link))
        soft = QtGui.QColor(accent)
        soft.setAlpha(45)
        grey = QtGui.QColor(text)
        grey.setAlpha(28)
        faint = QtGui.QColor(text)
        faint.setAlpha(120)
        height = self.card_height()
        for index, (name, path, box, lines) in enumerate(self.cards):
            (col, row) = (index % self.columns, index // self.columns)
            (left, top) = (col * (CARD_W + 8) + 2, row * (height + 8) + 2)
            card = QtCore.QRectF(left, top, CARD_W, height)
            painter.setPen(pen(grey))
            painter.setBrush(QtGui.QBrush(base))
            painter.drawRoundedRect(card, 8, 8)
            scale = min(
                (CARD_W - 2 * PAD) / max(box.width(), 1),
                (DRAW_H - 8) / max(box.height(), 1),
            )
            ox = left + (CARD_W - box.width() * scale) / 2 - box.x() * scale
            oy = top + PAD + 4 + box.bottom() * scale
            painter.save()
            painter.translate(ox, oy)
            painter.scale(scale, -scale)
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QBrush(text))
            painter.drawPath(path)
            painter.restore()
            y = top + PAD + DRAW_H
            painter.setPen(pen(text))
            bold = QtGui.QFont(painter.font())
            bold.setBold(True)
            painter.save()
            painter.setFont(bold)
            painter.drawText(
                QtCore.QRectF(left, y, CARD_W, LINE_H), int(QtCore.Qt.AlignCenter), name
            )
            painter.restore()
            for master, components, contours, auto, odd in lines:
                y += LINE_H
                painter.setPen(pen(faint))
                label = master if len(master) <= 9 else master[:8] + "…"
                if auto or odd:
                    painter.setPen(QtCore.Qt.NoPen)
                    painter.setBrush(
                        QtGui.QBrush(accent if auto else QtGui.QColor("#d33"))
                    )
                    painter.drawEllipse(
                        QtCore.QPointF(left + PAD - 4, y + LINE_H / 2), 3, 3
                    )
                    painter.setPen(pen(faint))
                painter.drawText(
                    QtCore.QRectF(left + PAD + 2, y, 66, LINE_H),
                    int(QtCore.Qt.AlignVCenter),
                    label,
                )
                x = left + PAD + 70
                x += self.badge(painter, x, y, f"{components} comp", soft, accent) + 4
                self.badge(painter, x, y, f"{contours} cont", grey, text)
