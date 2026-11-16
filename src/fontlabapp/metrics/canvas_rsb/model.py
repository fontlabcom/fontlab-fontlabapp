# this_file: src/fontlabapp/metrics/canvas_rsb/model.py
# SPDX-License-Identifier: Apache-2.0
"""Read laid-out glyph occurrences and paint an RSB foreground adaptation.

Behavior follows akufadhl/RSBline, Apache-2.0; implementation is original.
Use glyph, block and canvas maps in order. Glyph placement includes kerning.
The caller owns the overlay, polling and font/window binding. Paint consumes
immutable numeric records and never reads a native font or ends its painter.
"""

import math
import time
from dataclasses import dataclass
from typing import Any

from fontlabapp import _native
from fontlabapp.contours.affine import (
    apply,
    concat,
    from_qtransform,
    viewport_transform,
)
from fontlabapp.qt.safe import qt_list

Point = tuple[float, float]
Matrix = tuple[float, ...]


@dataclass(frozen=True)
class Marker:
    """One laid-out occurrence, including its own immutable pixel map."""

    name: str
    item: tuple[int, int]
    package_id: int
    glyph_id: int
    master: str
    active: bool
    transform: Matrix
    line: tuple[Point, Point]
    triangle: tuple[Point, Point, Point]
    stroke: float


def geometry(
    width: float,
    ascender: float,
    descender: float,
    x_height: float,
    angle: float,
    scale: float,
    direction: int,
) -> tuple[tuple[Point, Point], tuple[Point, Point, Point], float]:
    """Keep original italic shift, half-advance triangle and scale exponents.

    Direction0 marks the right advance edge; direction2 marks the left edge.
    Zero/negative advances are meaningful. Singular/non-finite inputs refuse.
    """
    values = width, ascender, descender, x_height, angle, scale
    if not all(math.isfinite(v) for v in values) or abs(angle) >= 90:
        raise ValueError("RSB metrics must be finite with an italic angle below90°.")
    if scale <= 0 or direction not in (0, 2):
        raise ValueError("RSB scale must be positive; choose LTR or RTL.")
    tangent, size = math.tan(math.radians(angle)), 10 / scale
    edge = width if direction == 0 else 0

    def shifted(x: float, y: float) -> Point:
        return x + tangent * (y - x_height / 2), y

    line = shifted(edge, ascender), shifted(edge, descender)
    triangle = (
        shifted(width / 2 - size, descender),
        shifted(width / 2, descender + size),
        shifted(width / 2 + size, descender),
    )
    if not all(math.isfinite(v) for p in (*line, *triangle) for v in p):
        raise ValueError("RSB geometry exceeds the finite coordinate range.")
    return line, triangle, scale**-0.9


def map_point(matrix: Matrix, point: Point) -> Point:
    """Map one point through a numeric Qt affine matrix."""
    return apply(matrix, point[0], point[1], finite=False)  # type: ignore[arg-type]


def matrix(transform: Any) -> Matrix:
    """Copy only the verified six affine terms; retain no native wrapper."""
    return from_qtransform(transform)


def compose(first: Matrix, second: Matrix) -> Matrix:
    """Apply first then second, matching native glyph × block × viewport.

    Callers test the result for finiteness and singularity themselves, so the
    shared ``concat`` runs unchecked here.
    """
    return concat(first, second, finite=False)  # type: ignore[arg-type]


def capture(
    canvas: Any, package: Any, direction: int, *, deadline: float | None = None
) -> tuple[Marker, ...]:
    """Read every bound-font glyph occurrence without selection or font writes.

    Poll outside paint. Bound native list conversion with GC off. Refuse an
    incomplete scan, changed master domain or missing layer as a whole.
    """
    deadline = time.monotonic() + 0.4 if deadline is None else deadline
    package_id, master, domain = package.id, package.master, tuple(package.masters)
    metrics = _native("fontlab").FontMetrics(package, master)
    viewport = viewport_transform(canvas, _native("PythonQt").QtCore.QPointF)
    values = metrics.ascender, metrics.descender, metrics.xHeight
    # FontLab uses the PostScript sign; the original Glyphs geometry is opposite.
    angle = -float(package.italicAngle_value)
    records = []
    for block in qt_list(canvas.textBlocks):
        if time.monotonic() >= deadline:
            raise TimeoutError(
                "RSB scan deadline exceeded; shorten the Glyph-window text."
            )
        if block.package.id != package.id:
            continue
        block_matrix = matrix(block.transform)
        for info in qt_list(lambda block=block: block.getAllGlyphs() or ()):
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    "RSB scan deadline exceeded; shorten the Glyph-window text."
                )
            glyph = info.glyph
            layer = (
                glyph.findLayer(master)
                if glyph is not None and not glyph.isNull
                else None
            )
            if layer is None or layer.isNull:
                raise ValueError("Glyph layer disappeared; reopen the RSB panel.")
            full = compose(compose(matrix(info.transform), block_matrix), viewport)
            scale = math.hypot(full[0], full[1])
            line, triangle, stroke = geometry(
                layer.advanceWidth,
                *values,
                angle,
                scale,
                direction,
            )
            records.append(
                Marker(
                    glyph.name,
                    (block.id, info.id),
                    package_id,
                    glyph.id,
                    master,
                    bool(info.isActive),
                    full,
                    line,
                    triangle,
                    stroke,
                )
            )
    if (package.id, package.master, tuple(package.masters)) != (
        package_id,
        master,
        domain,
    ):
        raise ValueError("Masters changed during the RSB scan; reopen the panel.")
    if time.monotonic() >= deadline:
        raise TimeoutError("RSB scan deadline exceeded; shorten the Glyph-window text.")
    return tuple(records)


def paint(painter: Any, records: tuple[Marker, ...], color: str) -> None:
    """Paint original line and red40% triangle; always restore the borrowed painter."""
    qt = _native("PythonQt")
    for record in records:
        painter.save()
        try:
            painter.setWorldTransform(qt.QtGui.QTransform(*record.transform), False)
            painter.setRenderHint(qt.QtGui.QPainter.Antialiasing)
            pen = qt.QtGui.QPen(qt.QtGui.QColor(color))
            pen.setWidthF(record.stroke)
            painter.setPen(pen)
            painter.drawLine(*(qt.QtCore.QPointF(*p) for p in record.line))
            painter.setPen(qt.QtCore.Qt.NoPen)
            painter.setBrush(qt.QtGui.QColor(255, 0, 0, 102))
            painter.drawPolygon(
                qt.QtGui.QPolygonF([qt.QtCore.QPointF(*p) for p in record.triangle])
            )
        finally:
            painter.restore()
