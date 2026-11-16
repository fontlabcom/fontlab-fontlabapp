# this_file: src/fontlabapp/proof/inspect/views.py
# SPDX-License-Identifier: Apache-2.0
"""Actual native outline painters shared by the three read-only Proof tools."""

from typing import Any

from fontlabapp import _native
from fontlabapp.proof.inspect.model import grid_scale, path_span

QtCore, QtGui = (_native("PythonQt").QtCore, _native("PythonQt").QtGui)


class ProofView(QtGui.QWidget):
    """Contain every painter/callback failure and release the active painter."""

    def paintEvent(self, event: Any) -> None:
        """Paint cached outlines only after checking the owning panel binding."""
        painter = None
        error = ""
        try:
            if self.before_draw is not None:
                self.before_draw()
            painter = QtGui.QPainter(self)
            if painter.isActive() is False:
                raise RuntimeError("Proof painter is not active.")
            self.draw(painter)
        except Exception as failure:  # noqa: BLE001 - contain the native paint boundary
            error = repr(failure)
        finally:
            if painter is not None:
                try:
                    if painter.end() is False:
                        raise RuntimeError("Proof painter could not end painting.")
                except Exception as failure:  # noqa: BLE001 - contain the native paint boundary
                    error = (error + "; " if error else "") + repr(failure)
        self.paint_error = error
        if error and self.on_error is not None:
            try:
                self.on_error(error)
            except Exception as failure:  # noqa: BLE001 - contain the native paint boundary
                self.paint_error += "; error hook: " + repr(failure)


class Grid(ProofView):
    """Custom painter: one cell per glyph x master, baseline and advance box shown faintly."""

    LABEL = 18

    def __init__(self, parent: Any = None) -> None:
        """Build the original controls and retain only owned native UI resources."""
        QtGui.QWidget.__init__(self, parent)
        self.before_draw = None
        self.paint_error = ""
        self.on_error = None
        self.cells = []
        self.masters = []
        self.frame = (-250, 750)
        self.cell = 120
        self.painted = 0

    def set_content(self, cells: Any, masters: Any, frame: Any, cell: Any) -> None:
        """Publish a complete cached proof and update its scrollable dimensions."""
        self.cells, self.masters, self.frame, self.cell = (cells, masters, frame, cell)
        self.painted = 0
        width = self.LABEL * 5 + len(masters) * (cell + 8)
        height = self.LABEL + len(cells) * (cell + self.LABEL + 8) + 8
        self.setMinimumSize(width, height)
        self.resize(max(width, self.width), height)
        self.update()

    def draw(self, painter: Any) -> None:
        """Paint the actual transformed outlines, advances, labels and missing slots."""
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        text = QtGui.QColor(self.palette.color(QtGui.QPalette.Text))
        faint = QtGui.QColor(text)
        faint.setAlpha(40)
        soft = QtGui.QColor(text)
        soft.setAlpha(140)
        _descender, ascender = self.frame
        scale = grid_scale(self.cells, self.frame, self.cell)
        left = self.LABEL * 5
        painter.setPen(soft)
        for column, master in enumerate(self.masters):
            x = left + column * (self.cell + 8)
            painter.drawText(
                QtCore.QRectF(x, 0, self.cell, self.LABEL),
                int(QtCore.Qt.AlignCenter),
                master,
            )
        self.painted = 0
        for row, (name, layers) in enumerate(self.cells):
            top = self.LABEL + row * (self.cell + self.LABEL + 8)
            painter.setPen(soft)
            painter.drawText(
                QtCore.QRectF(0, top, left - 8, self.cell),
                int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter),
                name,
            )
            for column, (master, path, advance) in enumerate(layers):
                x = left + column * (self.cell + 8)
                painter.setPen(QtGui.QPen(QtGui.QBrush(faint), 1.0))
                painter.setBrush(QtGui.QBrush())
                painter.drawRoundedRect(
                    QtCore.QRectF(x, top, self.cell, self.cell), 6, 6
                )
                if path is None:
                    painter.setPen(soft)
                    painter.drawText(
                        QtCore.QRectF(x, top, self.cell, self.cell),
                        int(QtCore.Qt.AlignCenter),
                        "–",
                    )
                    continue
                left_ink, right_ink = path_span(path, advance)
                offset = (
                    x
                    + (self.cell - (right_ink - left_ink) * scale) / 2.0
                    - left_ink * scale
                )
                baseline = top + self.cell * 0.06 + ascender * scale
                painter.drawLine(
                    QtCore.QPointF(x + 4, baseline),
                    QtCore.QPointF(x + self.cell - 4, baseline),
                )
                painter.save()
                painter.translate(offset, baseline)
                painter.scale(scale, 0 - scale)
                painter.fillPath(path, QtGui.QBrush(text))
                painter.restore()
                painter.setPen(soft)
                painter.drawText(
                    QtCore.QRectF(x, top + self.cell + 2, self.cell, self.LABEL),
                    int(QtCore.Qt.AlignCenter),
                    str(round(advance)),
                )
                self.painted += 1


class MasterRows(ProofView):
    """Custom painter: one labelled row per master."""

    def __init__(self, parent: Any = None) -> None:
        """Build the original controls and retain only owned native UI resources."""
        QtGui.QWidget.__init__(self, parent)
        self.before_draw = None
        self.paint_error = ""
        self.on_error = None
        self.rows, self.px_size, self.upm, self.frame = (
            [],
            48,
            1000.0,
            (-250.0, 750.0),
        )

    def set_content(self, rows: Any, size: Any, upm: Any, frame: Any) -> None:
        """Publish a complete cached proof and update its scrollable dimensions."""
        self.rows, self.px_size, self.upm, self.frame = (rows, size, float(upm), frame)
        scale = size / self.upm
        line = (frame[1] - frame[0]) * scale
        widest = max([sum((a for _, a in run)) for _, run, _ in rows] or [0]) * scale
        width, height = (int(widest) + 32, int(len(rows) * (line + 34)) + 8)
        self.setMinimumSize(width, height)
        self.resize(max(width, self.width), height)
        self.update()

    def draw(self, painter: Any) -> None:
        """Paint the actual transformed outlines, advances, labels and missing slots."""
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        text = QtGui.QColor(self.palette.color(QtGui.QPalette.Text))
        soft = QtGui.QColor(text)
        soft.setAlpha(130)
        faint = QtGui.QColor(text)
        faint.setAlpha(30)
        alert = QtGui.QColor("#d33")
        brush = QtGui.QBrush(text)
        scale = self.px_size / self.upm
        descender, ascender = self.frame
        line = (ascender - descender) * scale
        y = 4.0
        for master, run, width_units in self.rows:
            painter.setPen(soft)
            painter.drawText(
                QtCore.QRectF(16, y, self.width - 32, 18),
                int(QtCore.Qt.AlignLeft),
                f"{master}  ·  {width_units:g} units",
            )
            baseline = y + 22 + ascender * scale
            x = 16.0
            for path, advance in run:
                if path is None:
                    painter.setPen(QtGui.QPen(QtGui.QBrush(alert), 1.0))
                    painter.setBrush(QtGui.QBrush())
                    painter.drawRect(
                        QtCore.QRectF(
                            x + 1,
                            baseline - self.px_size * 0.7,
                            advance * scale - 2,
                            self.px_size * 0.7,
                        )
                    )
                else:
                    painter.save()
                    painter.translate(x, baseline)
                    painter.scale(scale, 0 - scale)
                    painter.fillPath(path, brush)
                    painter.restore()
                x += advance * scale
            y += line + 34
            painter.setPen(QtGui.QPen(QtGui.QBrush(faint), 1.0))
            painter.drawLine(
                QtCore.QPointF(16, y - 6), QtCore.QPointF(self.width - 16, y - 6)
            )


class WaterfallView(ProofView):
    """Custom painter: one line per size, glyphs filled with the palette's text colour."""

    GUTTER = 44

    def __init__(self, parent: Any = None) -> None:
        """Build the original controls and retain only owned native UI resources."""
        QtGui.QWidget.__init__(self, parent)
        self.before_draw = None
        self.paint_error = ""
        self.on_error = None
        self.run, self.sizes, self.upm, self.ascender = ([], [], 1000.0, 800.0)
        self.width_units = 0

    def set_content(self, glyphs: Any, sizes: Any, upm: Any, ascender: Any) -> None:
        """Publish a complete cached proof and update its scrollable dimensions."""
        self.run, self.sizes, self.upm, self.ascender = (
            glyphs,
            sizes,
            float(upm),
            float(ascender),
        )
        self.width_units = sum((advance for _, advance in glyphs))
        height = int(sum(size * 1.3 + 8 for size in sizes)) + 16
        width = (
            int(
                self.GUTTER
                + max([self.width_units * s / self.upm for s in sizes] or [0])
            )
            + 24
        )
        self.setMinimumSize(width, height)
        self.resize(max(width, self.width), height)
        self.update()

    def draw(self, painter: Any) -> None:
        """Paint the actual transformed outlines, advances, labels and missing slots."""
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        text = QtGui.QColor(self.palette.color(QtGui.QPalette.Text))
        soft = QtGui.QColor(text)
        soft.setAlpha(120)
        alert = QtGui.QColor("#d33")
        brush = QtGui.QBrush(text)
        y = 8.0
        for size in self.sizes:
            scale = size / self.upm
            baseline = y + self.ascender * scale * 1.05
            painter.setPen(soft)
            painter.drawText(
                QtCore.QRectF(0, baseline - 14, self.GUTTER - 10, 16),
                int(QtCore.Qt.AlignRight | QtCore.Qt.AlignBottom),
                f"{size:g}",
            )
            x = float(self.GUTTER)
            for path, advance in self.run:
                if path is None:
                    painter.setPen(QtGui.QPen(QtGui.QBrush(alert), 1.0))
                    painter.setBrush(QtGui.QBrush())
                    painter.drawRect(
                        QtCore.QRectF(
                            x + 1,
                            baseline - size * 0.7,
                            advance * scale - 2,
                            size * 0.7,
                        )
                    )
                else:
                    painter.save()
                    painter.translate(x, baseline)
                    painter.scale(scale, 0 - scale)
                    painter.fillPath(path, brush)
                    painter.restore()
                x += advance * scale
            y += size * 1.3 + 8
