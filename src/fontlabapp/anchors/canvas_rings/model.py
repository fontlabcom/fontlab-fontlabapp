# this_file: src/fontlabapp/anchors/canvas_rings/model.py
# SPDX-License-Identifier: Apache-2.0
"""Original Apache-2.0 adaptation of mekkablue's duplicate-anchor rings.

No corpus source is copied. Explicit handle sizes replace Glyphs preferences.
Caller owns refresh/lifecycle; no automatic tool gating or background claim.
"""

import math
import time
from dataclasses import dataclass
from typing import Any

from fontlabapp import _native
from fontlabapp.contours.affine import viewport_transform
from fontlabapp.qt.safe import qt_list
from fontlabapp.metrics.canvas_rsb.model import Matrix, Point, compose, matrix


@dataclass(frozen=True)
class Ring:
    """One matching unordered anchor pair, placed at its first position."""

    pair: tuple[int, int]
    center: Point
    diameter: float
    outer: float
    inner: float


@dataclass(frozen=True)
class Occurrence:
    """Copy of one actual native glyph item, including zero-ring sources."""

    item: tuple[int, int]
    glyph_id: int
    name: str
    active: bool
    transform: Matrix
    anchors: tuple[tuple[str, Point], ...]
    rings: tuple[Ring, ...]


@dataclass(frozen=True)
class Snapshot:
    """Plain binding and complete occurrence data; retain no native wrappers."""

    package_id: int
    canvas_id: int
    master: str
    masters: tuple[str, ...]
    occurrences: tuple[Occurrence, ...]


def check_deadline(deadline: float) -> None:
    """Bound native refresh and quadratic pair search without partial results."""
    if time.monotonic() >= deadline:
        raise TimeoutError("Anchor-ring scan deadline exceeded; shorten the text.")


def rings(
    points: tuple[Point, ...],
    scale: float,
    *,
    handle_size: int = 8,
    deadline: float | None = None,
) -> tuple[Ring, ...]:
    """Keep distance<1.0, all pairs and original diameter/stroke exponents.

    Handle sizes5/8/12 correspond to the original three Glyphs preferences.
    Three coincident anchors yield three rings, without deduplication.
    """
    deadline = time.monotonic() + 0.4 if deadline is None else deadline
    check_deadline(deadline)
    if not math.isfinite(scale) or scale <= 0 or handle_size not in (5, 8, 12):
        raise ValueError("Use a positive finite scale and handle size5,8 or12.")
    diameter, outer, inner = 2 * handle_size * scale**-0.9, 6 / scale, 2 / scale
    if not all(math.isfinite(v) for v in (diameter, outer, inner)):
        raise ValueError("Anchor-ring dimensions exceed the finite coordinate range.")
    for point in points:
        check_deadline(deadline)
        if not all(math.isfinite(v) for v in point):
            raise ValueError("Anchor coordinates must be finite.")
    result = []
    for i, point in enumerate(points):
        for j in range(i + 1, len(points)):
            check_deadline(deadline)
            other = points[j]
            if math.hypot(point[0] - other[0], point[1] - other[1]) < 1:
                result.append(Ring((i, j), point, diameter, outer, inner))
    return tuple(result)


def capture(
    canvas: Any,
    package: Any,
    *,
    handle_size: int = 8,
    deadline: float | None = None,
) -> Snapshot:
    """Copy glyph×block×viewport occurrences with GC safety and binding guards."""
    deadline = time.monotonic() + 0.4 if deadline is None else deadline
    check_deadline(deadline)
    binding = package.id, canvas.id, package.master, tuple(package.masters)
    viewport = viewport_transform(canvas, _native("PythonQt").QtCore.QPointF)
    records = []
    for block in qt_list(canvas.textBlocks):
        check_deadline(deadline)
        if block.package.id != binding[0]:
            continue
        block_map = matrix(block.transform)
        for info in qt_list(lambda block=block: block.getAllGlyphs() or ()):
            check_deadline(deadline)
            glyph = info.glyph
            layer = (
                glyph.findLayer(binding[2])
                if glyph is not None and not glyph.isNull
                else None
            )
            if layer is None or layer.isNull:
                raise ValueError(
                    "Glyph layer disappeared; reopen the anchor-ring panel."
                )
            full = compose(compose(matrix(info.transform), block_map), viewport)
            if (
                not all(math.isfinite(v) for v in full)
                or full[0] * full[3] == full[1] * full[2]
            ):
                raise ValueError("Invalid or singular native occurrence transform.")
            anchors = []
            for pin in qt_list(lambda layer=layer: layer.anchors):
                check_deadline(deadline)
                position = pin.point
                anchors.append((pin.name, (float(position.x()), float(position.y()))))
            markers = rings(
                tuple(p for _, p in anchors),
                math.hypot(full[0], full[1]),
                handle_size=handle_size,
                deadline=deadline,
            )
            records.append(
                Occurrence(
                    (block.id, info.id),
                    glyph.id,
                    glyph.name,
                    bool(info.isActive),
                    full,
                    tuple(anchors),
                    markers,
                )
            )
    if (package.id, canvas.id, package.master, tuple(package.masters)) != binding:
        raise ValueError(
            "Font, canvas or master domain changed during anchor-ring scan."
        )
    check_deadline(deadline)
    return Snapshot(*binding, tuple(records))


def paint(painter: Any, snapshot: Snapshot) -> None:
    """Draw red6/scale then yellow2/scale outlines; restore borrowed painter."""
    qt = _native("PythonQt")
    for item in snapshot.occurrences:
        if not item.rings:
            continue
        painter.save()
        try:
            painter.setWorldTransform(qt.QtGui.QTransform(*item.transform), False)
            painter.setRenderHint(qt.QtGui.QPainter.Antialiasing)
            # PythonQt exposes setBrush(QBrush) without enum conversion.
            painter.setBrush(qt.QtGui.QBrush())
            for ring in item.rings:
                x, y = ring.center
                rect = qt.QtCore.QRectF(
                    x - ring.diameter / 2,
                    y - ring.diameter / 2,
                    ring.diameter,
                    ring.diameter,
                )
                for color, width in (
                    ((255, 0, 0), ring.outer),
                    ((255, 255, 0), ring.inner),
                ):
                    pen = qt.QtGui.QPen(qt.QtGui.QColor(*color))
                    pen.setWidthF(width)
                    painter.setPen(pen)
                    painter.drawEllipse(rect)
        finally:
            painter.restore()
