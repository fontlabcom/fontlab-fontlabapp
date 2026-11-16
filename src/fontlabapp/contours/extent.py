# this_file: src/fontlabapp/contours/extent.py
# SPDX-License-Identifier: Apache-2.0
"""Measure the vertical extent of a layer from its outline nodes.

What: ``vertical_extent(layer)`` returns ``(ymin, ymax)`` of every contour of
every shape of ``layer``, or ``None`` when no contour has a node.

Why: FontLab keeps ``flLayer.boundingBox`` and ``flShape.boundingBox`` as a
cache. After a Python node move, the cache stays stale, also after
``notifyChangesApplied`` (fl#8575, FontLab 9.0.9790). This module never reads
a ``boundingBox`` and never calls ``update()``, so the read has no side effects.

How: each shape's contours are mapped through ``shape.transform`` (an affine
QTransform, read through ``m11()`` … ``m33()``), so a component counts at its
placement, as in ``masters.layer_contours``. Shapes without contours (stickers,
empty shapes) give nothing. Nodes come from ``contour.nodes()`` as ``node.x``,
``node.y`` and their kind: ``node.isOn()`` (on-curve), ``node.isCurve()``
(cubic control, ``flNode::Curve``) or else a quadratic control
(``flNode::Off``, ``node.isOff()``; flnode.h). The kind decides each segment,
not ``contour.isTT``: FontLab sets ``isTT`` when any node is a quadratic
control, so one contour can mix both kinds (flcontour.cpp). As in FontLab's
contour enumerator (flconturenum.h), an implied on-curve midpoint lies only
between two consecutive ``Off`` nodes. Each segment between two on-curve nodes
gives its end y values and its exact y extremes: the roots of the cubic
derivative in (0, 1) for two ``Curve`` controls, or the one extreme for one
``Off`` control. A closed contour also gives its closing segment.

Not counted, by design: stroke thickness (``maxThickness``, which
``flShape.boundingBox`` adds), because zones measure the outline; and the
per-contour ``contour.transform()``, which is identity outside an interactive
transform (flshapedata.cpp).
"""

from collections.abc import Iterable, Sequence
from math import sqrt
from typing import Any

Point = tuple[float, float]
#: Node kinds: on-curve, cubic control (flNode::Curve), quadratic control (flNode::Off).
ON, CURVE, OFF = "on", "curve", "off"
Node = tuple[Point, str]
#: Coefficients below this size count as zero (font units).
EPSILON = 1e-12
#: Control kinds a segment between two on-curve nodes may have.
SEGMENT_CONTROLS = ([], [OFF], [CURVE, CURVE])


def _matrix(transform: Any) -> tuple[float, ...]:
    """Return the nine QTransform values; refuse a projective transform."""
    m = tuple(float(getattr(transform, f"m{i}{j}")()) for i in (1, 2, 3) for j in (1, 2, 3))
    if (m[2], m[5], m[8]) != (0.0, 0.0, 1.0):
        raise ValueError("Projective shape transforms are unsupported.")
    return m


def _map(m: Sequence[float], x: float, y: float) -> Point:
    """Map ``(x, y)`` as ``QTransform.map`` does for an affine transform."""
    return m[0] * x + m[3] * y + m[6], m[1] * x + m[4] * y + m[7]


def cubic_extremes(p0: float, p1: float, p2: float, p3: float) -> list[float]:
    """Return the values of a cubic Bezier coordinate at its turning points in (0, 1)."""
    a, b, c = -p0 + 3 * p1 - 3 * p2 + p3, 2 * (p0 - 2 * p1 + p2), p1 - p0
    if abs(a) < EPSILON:
        roots = [] if abs(b) < EPSILON else [-c / b]
    else:
        discriminant = b * b - 4 * a * c
        roots = [] if discriminant < 0 else [(-b + s * sqrt(discriminant)) / (2 * a) for s in (1, -1)]
    return [
        (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t * t * p2 + t**3 * p3
        for t in roots
        if 0 < t < 1
    ]


def quadratic_extremes(p0: float, p1: float, p2: float) -> list[float]:
    """Return the value of a quadratic Bezier coordinate at its turning point in (0, 1)."""
    denominator = p0 - 2 * p1 + p2
    if abs(denominator) < EPSILON:
        return []
    t = (p0 - p1) / denominator
    return [(1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t * t * p2] if 0 < t < 1 else []


def _implied(nodes: list[Node], closed: bool) -> list[Node]:
    """Insert the implied on-curve midpoint between two consecutive ``Off`` nodes."""
    result: list[Node] = []
    count = len(nodes)
    for index, (point, kind) in enumerate(nodes):
        result.append((point, kind))
        if index + 1 == count and not closed:
            break
        following, next_kind = nodes[(index + 1) % count]
        if kind == OFF and next_kind == OFF:
            middle = ((point[0] + following[0]) / 2, (point[1] + following[1]) / 2)
            result.append((middle, ON))
    return result


def segments(nodes: list[Node], closed: bool) -> Iterable[tuple[Point, ...]]:
    """Yield the line, quadratic and cubic segments of one contour, in order."""
    nodes = _implied(nodes, closed)
    first = next((i for i, (_, kind) in enumerate(nodes) if kind == ON), None)
    if first is None or (not closed and first != 0):
        raise ValueError("A contour must start at an on-curve node.")
    sequence = nodes[first:] + nodes[:first] + [nodes[first]] if closed else nodes
    start, controls = sequence[0][0], []
    for point, kind in sequence[1:]:
        if kind != ON:
            controls.append((point, kind))
            continue
        if [k for _, k in controls] not in SEGMENT_CONTROLS:
            raise ValueError("A segment needs no control, one quadratic or two cubic controls.")
        yield (start, *(p for p, _ in controls), point)
        start, controls = point, []
    if controls:
        raise ValueError("An open contour must end at an on-curve node.")


def contour_ys(nodes: list[Node], closed: bool) -> list[float]:
    """Return the end and extreme y values of every segment of one contour."""
    ys = [point[1] for point, kind in nodes if kind == ON]
    for segment in segments(nodes, closed):
        values = [point[1] for point in segment]
        ys.append(values[-1])  # also an implied on-curve point
        if len(values) == 3:
            ys += quadratic_extremes(*values)
        elif len(values) == 4:
            ys += cubic_extremes(*values)
    return ys


def _kind(node: Any) -> str:
    """Return ON, CURVE or OFF from the host predicates ``isOn()`` and ``isCurve()``."""
    if node.isOn():
        return ON
    return CURVE if node.isCurve() else OFF


def vertical_extent(layer: Any) -> tuple[float, float] | None:
    """Return ``(ymin, ymax)`` of the outlines of ``layer``, or ``None`` when empty.

    Reads ``layer.shapes``, ``shape.transform``, ``shape.contours``,
    ``contour.nodes()``, ``contour.closed``, ``node.x``, ``node.y``,
    ``node.isOn()`` and ``node.isCurve()`` only; never ``boundingBox``
    (fl#8575). Raises ``ValueError`` for an outline it cannot read (bad
    topology, projective transform).
    """
    ys: list[float] = []
    for shape in layer.shapes:
        contours = list(shape.contours)
        if not contours:
            continue
        matrix = _matrix(shape.transform)
        for contour in contours:
            nodes = [(_map(matrix, float(n.x), float(n.y)), _kind(n)) for n in contour.nodes()]
            if nodes:
                ys += contour_ys(nodes, bool(contour.closed))
    return (min(ys), max(ys)) if ys else None


__all__ = [
    "contour_ys",
    "cubic_extremes",
    "quadratic_extremes",
    "segments",
    "vertical_extent",
]
