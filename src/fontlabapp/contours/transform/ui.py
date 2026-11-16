# this_file: src/fontlabapp/contours/transform/ui.py
# SPDX-License-Identifier: Apache-2.0
"""``OutlinePreview`` and the ``TransformPanel`` base of Transform and Slant (PythonQt).

Load it through ``fontlabapp.contours.transform.model.panel_type()``, inside
FontLab only: this module imports PythonQt at load time, like
``_outline_panel``. The planner, the writer and the preview geometry live in
``fontlabapp.contours.transform.model``.

``paintEvent`` never lets an exception out and always ends the painter: an
exception that escapes a PythonQt paint handler while a QPainter is active
crashes FontLab. ``closeEvent`` drops the painter callback first.
"""

from collections.abc import Callable
from typing import Any

import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - the package __getattr__ is native
import fontlabapp.contours.transform.model as outline_transform  # noqa: PLR0402 - the package __getattr__ is native
import fontlabapp.contours.writer as outline_writer  # noqa: PLR0402 - the package __getattr__ is native
from fontlabapp import _native
from fontlabapp.contours.panel.ui import OutlinePanel

QtCore, QtGui = _native("PythonQt").QtCore, _native("PythonQt").QtGui


class OutlinePreview(QtGui.QWidget):
    """Paint one layer before (faint fill) and after (accent outline) the change."""

    def __init__(self, parent: Any = None) -> None:
        """Empty preview; ``report`` receives a drawing failure text."""
        QtGui.QWidget.__init__(self, parent)
        self.before: list[list[outline_writer.Point]] = []
        self.after: list[list[outline_writer.Point]] = []
        self.guide_y: float | None = None
        self.report: Callable[[str], None] | None = None
        self.paint_error = ""
        self.setMinimumHeight(220)

    def show_outlines(
        self,
        before: list[list[outline_writer.Point]],
        after: list[list[outline_writer.Point]],
        guide_y: float | None,
    ) -> None:
        """Keep plain point lists (no native objects) and repaint."""
        self.before, self.after, self.guide_y = before, after, guide_y
        self.update()

    def paintEvent(self, event: Any) -> None:
        """Paint; an exception never leaves paintEvent, and the painter always ends."""
        self.paint_error = ""
        painter = QtGui.QPainter(self)
        try:
            self.draw_outlines(painter)
        except Exception as error:  # noqa: BLE001 - an exception here can crash FontLab
            self.paint_error = repr(error)
            if self.report is not None:
                self.report(f"Preview failed: {self.paint_error}")
        finally:
            painter.end()

    def draw_outlines(self, painter: Any) -> None:
        """Background, optional guide line, faint 'before', accent 'after'."""
        palette = self.palette
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.fillRect(
            0, 0, self.width, self.height, palette.color(QtGui.QPalette.Base)
        )
        before, after = (
            outline_transform.outline_path(self.before),
            outline_transform.outline_path(self.after),
        )
        box = before.boundingRect().united(after.boundingRect())
        painter.setTransform(
            QtGui.QTransform(*outline_transform.fit(box, self.width, self.height))
        )
        ink_color = QtGui.QColor(palette.color(QtGui.QPalette.WindowText))
        if self.guide_y is not None:
            guide = QtGui.QColor(ink_color)
            guide.setAlpha(70)
            dash = QtGui.QPen(guide)
            dash.setCosmetic(True)
            dash.setStyle(QtCore.Qt.DashLine)
            painter.setPen(dash)
            left, right = box.x() - 40, box.x() + box.width() + 40
            painter.drawLine(
                QtCore.QPointF(left, self.guide_y), QtCore.QPointF(right, self.guide_y)
            )
        ink_color.setAlpha(45)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QBrush(ink_color))
        painter.drawPath(before)
        accent = QtGui.QColor(palette.color(QtGui.QPalette.Link))
        pen = QtGui.QPen(accent)
        pen.setCosmetic(True)
        pen.setWidthF(1.6)
        painter.setPen(pen)
        fill = QtGui.QColor(accent)
        fill.setAlpha(40)
        painter.setBrush(QtGui.QBrush(fill))
        painter.drawPath(after)


class TransformPanel(OutlinePanel):
    """OutlinePanel with an outline preview of the first selected glyph."""

    def build_extra(self, root: Any) -> None:
        """Add the preview between the form and the table."""
        self.preview = OutlinePreview()
        self.preview.report = self.paint_report
        root.addWidget(self.preview, 2)

    def paint_report(self, text: str) -> None:
        """Show a drawing failure in the status line."""
        self.slot_error = text
        self.status.setText(text)

    def preview_matrix(
        self, layer: Any
    ) -> tuple[outline_transform.Affine, float | None]:
        """Subclass hook: (matrix, guide y) for the preview layer."""
        raise NotImplementedError

    def after_refresh(self) -> None:
        """Paint the current-master layer of the first glyph that may change."""
        layer = None
        if self.package is not None:
            for glyph in self.glyphs:
                if not history.refusal(
                    self.facts,
                    glyph.name,
                    "geometry",
                    allow_bases=self.bases.isChecked(),
                ):
                    found = outline_writer.layer_of(glyph, self.current_master)
                    if found is not None and not found.autoLayer:
                        layer = found
                        break
        if layer is None:
            self.preview.show_outlines([], [], None)
            return
        try:
            matrix, guide = self.preview_matrix(layer)
        except ValueError:
            self.preview.show_outlines([], [], None)
            return
        before = outline_transform.layer_outline(layer)
        self.preview.show_outlines(
            before, outline_transform.mapped(before, matrix), guide
        )

    def closeEvent(self, event: Any) -> None:
        """Drop the painter callback first, then close as every panel does."""
        self.preview.report = None
        OutlinePanel.closeEvent(self, event)
