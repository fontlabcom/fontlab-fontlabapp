# this_file: src/fontlabapp/plugins/geometry.py
# SPDX-License-Identifier: Apache-2.0
"""Small pure contour-segment operations shared by reporter computations."""

from itertools import pairwise
from math import comb, hypot, radians, tan

from .snapshot import Contour, Node


def segments(contour: Contour) -> tuple[tuple[Node, ...], ...]:
    """Split lines, quadratic and cubic segments; skip longer control runs."""
    nodes = contour.nodes
    on = [index for index, node in enumerate(nodes) if node.on_curve]
    if len(on) < 2:
        return ()
    pairs = list(pairwise(on))
    if contour.closed:
        pairs.append((on[-1], on[0]))
    rows = []
    for start, end in pairs:
        row = (
            nodes[start : end + 1] if end > start else nodes[start:] + nodes[: end + 1]
        )
        # Three or more off-curves may imply TrueType on-curves. Without curve
        # type in the snapshot, skip that run rather than mismeasure a segment.
        if len(row) in (2, 3, 4):
            rows.append(row)
    return tuple(rows)


def neighbours(contour: Contour, index: int) -> tuple[Node | None, Node | None]:
    """Return neighbours without wrapping the ends of an open contour."""
    nodes = contour.nodes
    before = nodes[index - 1] if index else (nodes[-1] if contour.closed else None)
    after = (
        nodes[index + 1]
        if index + 1 < len(nodes)
        else (nodes[0] if contour.closed else None)
    )
    return before, after


def point_at(segment: tuple[Node, ...], t: float) -> tuple[float, float]:
    """Evaluate a line, quadratic or cubic segment at fractional position t."""
    n = len(segment) - 1
    weights = tuple(comb(n, i) * (1 - t) ** (n - i) * t**i for i in range(n + 1))
    return (
        sum(node.x * weight for node, weight in zip(segment, weights, strict=True)),
        sum(node.y * weight for node, weight in zip(segment, weights, strict=True)),
    )


def length(segment: tuple[Node, ...], steps: int = 25) -> float:
    """Measure a line exactly and a Bézier by uniform flattening."""
    if len(segment) == 2:
        start, end = segment
        return hypot(end.x - start.x, end.y - start.y)
    previous, total = (segment[0].x, segment[0].y), 0.0
    for index in range(1, steps + 1):
        current = point_at(segment, index / steps)
        total += hypot(current[0] - previous[0], current[1] - previous[1])
        previous = current
    return total


def flatten(contour: Contour, steps: int = 16) -> tuple[tuple[float, float], ...]:
    """Polyline of a contour, curves at ``steps`` per segment, no repeated start."""
    points: list[tuple[float, float]] = []
    segs = segments(contour)
    for seg in segs:
        if len(seg) == 2:
            points.append((seg[0].x, seg[0].y))
        else:
            points += [point_at(seg, i / steps) for i in range(steps)]
    if segs and not contour.closed:
        points.append((segs[-1][-1].x, segs[-1][-1].y))
    return tuple(points)


def fill_points(
    contours: tuple[Contour, ...], steps: int = 16
) -> tuple[tuple[float, float], ...]:
    """One odd-even polygon for all contours so counters stay open.

    Each flattened contour is closed back to its own first point; the first
    points are then retraced in reverse so the bridging edges cancel in pairs.
    """
    loops = [p for c in contours if len(p := flatten(c, steps)) >= 3]
    points = [pt for loop in loops for pt in (*loop, loop[0])]
    points += [loop[0] for loop in reversed(loops[:-1])]
    return tuple(points)


def shear(
    points: tuple[tuple[float, float], ...], slant_deg: float, pivot_y: float
) -> tuple[tuple[float, float], ...]:
    """Slant points by ``slant_deg`` (top leans right when positive) about a height."""
    k = tan(radians(slant_deg))
    return tuple((x + k * (y - pivot_y), y) for x, y in points)
