# this_file: src/fontlabapp/fontui/sequence_canvas.py
# SPDX-License-Identifier: Apache-2.0
"""Original sequence painting; open contours stay open in both directions."""

from math import ceil, isfinite
from typing import Any
from weakref import ref as _ref

from fontTools.pens.qtPen import QtPen
from fontTools.pens.recordingPen import replayRecording
from PythonQt import QtCore, QtGui

from fontlabapp.qt.events.key import key_press_handler
from fontlabapp.fontui._canvas_palette import _canvas_colors
from fontlabapp.fontui.model import partition_paths
from fontlabapp.fontui.wrap import wrap

# Light-theme values; _canvas_colors swaps them for dark or palette colours.
_LIGHT = {"background": "white", "glyph": "#303030", "outline": "#303030", "missing": "#b04040"}


def create_canvas(owner: Any, parent: Any) -> Any:
    try:
        owner_ref = _ref(owner)
    except TypeError:
        # Only test doubles (types.SimpleNamespace) reach this branch: the real
        # Sequence supports weak references. Such owners are held strongly.
        def owner_ref():
            return owner

    class Canvas(QtGui.QWidget):
        def paintEvent(self, event: Any) -> None:
            owner = owner_ref()
            if owner is not None:
                paint(owner, self)

        def mousePressEvent(self, event: Any) -> None:
            owner = owner_ref()
            if owner is None:
                event.ignore()
                return
            owner.select_at(event.pos().x(), event.pos().y())
            event.accept()

        keyPressEvent = key_press_handler(
            QtGui.QWidget, lambda widget, event: (owner := owner_ref()) is not None and owner.select_key(event.key())
        )

    canvas = Canvas(parent)
    canvas.setFocusPolicy(QtCore.Qt.StrongFocus)
    canvas.setAccessibleName("Glyph sequence; select occurrences with arrow keys")
    return canvas


def place(owner: Any, occurrence: Any) -> tuple[float, float]:
    """Pixel x of the occurrence's origin and its line's baseline."""
    x, line = owner.positions[occurrence.index]
    return owner.origin_x + x * owner.scale, owner.baseline + line * owner.line_height


def reveal(owner: Any, occurrence: Any) -> None:
    x, baseline = place(owner, occurrence)
    owner.scroll.ensureVisible(
        int(x + occurrence.advance * owner.scale / 2), int(baseline), 20, 20
    )


def prepare(owner: Any) -> None:
    info = owner.font.info
    upm = 1000 if info.unitsPerEm is None else float(info.unitsPerEm)
    if not isfinite(upm) or upm <= 0:
        raise ValueError("Font unitsPerEm must be positive and finite")
    top = upm * 0.8 if info.ascender is None else info.ascender
    bottom = upm * -0.2 if info.descender is None else info.descender
    owner.scale = float(owner.size_control.value) / upm
    width, owner.wrap_width = None, None
    if owner.wrap_control.checked:
        owner.wrap_width = owner.scroll.viewport().width
        width = (owner.wrap_width - 40) / owner.scale
    owner.positions = wrap(owner.run.glyphs, width, owner.run.direction)
    left = right = 0.0
    for occurrence, (x, _) in zip(owner.run.glyphs, owner.positions):
        left, right = min(left, x), max(right, x + occurrence.advance)
        data = owner.outlines.get(occurrence.name)
        if data is not None and data.bounds is not None:
            x0, y0, x1, y1 = data.bounds
            left, right = min(left, x + x0), max(right, x + x1)
            bottom, top = min(bottom, y0), max(top, y1)
    lines = 1 + max((line for _, line in owner.positions), default=0)
    owner.line_height = (top - bottom) * owner.scale + 20
    owner.origin_x, owner.baseline = 20 - left * owner.scale, 20 + top * owner.scale
    owner.canvas.resize(
        max(400, ceil((right - left) * owner.scale + 40)),
        max(220, ceil(lines * owner.line_height + 40)),
    )


def _draw_glyph(owner: Any, painter: Any, occurrence: Any, colors: dict[str, str]) -> None:
    painter.save()
    try:
        painter.translate(*place(owner, occurrence))
        painter.scale(owner.scale, -owner.scale)
        pen = QtGui.QPen(QtGui.QColor(colors["outline"]))
        pen.setWidthF(1 / owner.scale)
        painter.setPen(pen)
        closed, opened = partition_paths(owner.outlines[occurrence.name].recording)
        for recording, fill in ((closed, True), (opened, False)):
            path = QtGui.QPainterPath()
            path.setFillRule(QtCore.Qt.WindingFill)
            replayRecording(recording, QtPen(None, path=path))
            painter.setBrush(
                QtGui.QBrush(QtGui.QColor(colors["glyph"]))
                if fill
                else QtGui.QBrush(QtCore.Qt.NoBrush)
            )
            painter.drawPath(path)
    finally:
        painter.restore()


def paint(owner: Any, canvas: Any) -> None:
    painter = QtGui.QPainter(canvas)
    colors = _canvas_colors(canvas, _LIGHT)
    try:
        painter.fillRect(canvas.rect, QtGui.QColor(colors["background"]))
        if owner.closed or owner.run is None:
            return
        owner.font.keys()  # Detect document closure before drawing cached paths.
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        for occurrence in owner.run.glyphs:
            x, baseline = place(owner, occurrence)
            span = occurrence.advance * owner.scale  # negative advances span leftwards
            rect = QtCore.QRectF(
                min(x, x + span),
                baseline - owner.baseline + 10,
                max(4, abs(span)),
                owner.line_height - 10,
            )
            if occurrence.index == owner.selected_index:
                painter.fillRect(rect, QtGui.QColor(colors["selection_background"]))
            if occurrence.name is not None:
                if occurrence.name not in owner.font:
                    raise ValueError(f"Missing glyph: {occurrence.name}")
                _draw_glyph(owner, painter, occurrence, colors)
            else:
                painter.setPen(QtGui.QPen(QtGui.QColor(colors["missing"])))
                painter.setBrush(QtGui.QBrush(QtCore.Qt.NoBrush))
                painter.drawRect(rect)
                painter.drawText(int(rect.left() + 3), int(baseline), occurrence.label)
    except Exception as error:  # noqa: BLE001 - never let a paint failure escape into Qt
        owner.fail(error)
        painter.fillRect(canvas.rect, QtGui.QColor(colors["background"]))
    finally:
        painter.end()
