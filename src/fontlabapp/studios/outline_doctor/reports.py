# this_file: src/fontlabapp/studios/outline_doctor/reports.py
# SPDX-License-Identifier: Apache-2.0
"""Outline Doctor read-only reports: Open Contours, Close But No Cigar, Dangerous Offcurves.

What: three planners that return ``Issue`` rows with no edit. Open Contours
lists every open contour with its node count and end gap; Close But No Cigar
(after Simon Cozens' glyphmonkey script, MIT) lists angles within 2° of
horizontal or vertical, segment lengths within 5 % of a master stem and nodes
within 2 units of zero or a vertical metric; Dangerous Offcurves lists cubic
handles closer than 0.05 units to their own curve on all four axis probes.
Why: they are the Scan tab's whole-font and selection reports; they never write.
"""

import math
from collections.abc import Mapping
from typing import Any

from ..transform_studio.geometry import apply
from ..transform_studio.native import matrix_of
from .model import Context, Issue, plural

ANGLE = 2.0
STEM = 0.05
METRIC = 2.0
THRESHOLD = 0.05
PROBE = 10000.0
STEPS = 50
TT_ERROR = "TrueType curves are unsupported; no partial report."
COMPOSITE_ERROR = "Generated shape geometry is unsupported; no partial report."


def own_paths(layer: Any) -> list[tuple[int, list[tuple[float, float, bool]], bool]]:
    """(contour number, glyph-space (x, y, off) nodes, closed) of every own contour."""
    found, number = [], 0
    for shape in layer.shapes:
        if shape.isComponent:
            continue
        if getattr(shape, "isComposite", False):
            raise ValueError(COMPOSITE_ERROR)
        matrix = matrix_of(shape.transform)
        for contour in shape.contours:
            nodes = [(*apply(matrix, float(n.x), float(n.y)), not n.isOn()) for n in contour.nodes()]
            found.append((number, nodes, bool(contour.closed)))
            number += 1
    return found


# Open Contours -----------------------------------------------------------------
def plan_open(layer: Any, options: Mapping[str, Any], context: Context) -> list[Issue]:
    rows = []
    for number, nodes, closed in own_paths(layer):
        if closed or not nodes:
            continue
        gap = round(math.hypot(nodes[-1][0] - nodes[0][0], nodes[-1][1] - nodes[0][1]), 1)
        rows.append(Issue(f"contour {number + 1}", plural(len(nodes), "node"), f"gap {gap:g}",
                          problem="gap" if gap > 0 else "", marks=((number, 0), (number, len(nodes) - 1))))  # fmt: skip
    return rows


# Close But No Cigar ------------------------------------------------------------
def segments(nodes: list[tuple[float, float, bool]]) -> list[tuple]:
    """glyphmonkey's segments: the first starts at the last node, even for open paths."""
    if not nodes:
        return []
    result, pending = [], [nodes[-1][:2]]
    for x, y, off in nodes:
        pending.append((x, y))
        if not off:
            if len(pending) not in (2, 4):
                raise ValueError("Only line or cubic topology is supported.")
            result.append(tuple(pending))
            pending = [(x, y)]
    return result


def measure(points: tuple) -> tuple[float, float]:
    """Endpoint angle and line chord or the original 50-step cubic length."""
    dx, dy = (points[-1][i] - points[0][i] for i in (0, 1))
    angle = math.degrees(math.atan2(dy, dx))
    if len(points) == 2:
        return angle, math.sqrt(dx * dx + dy * dy)
    t, length, previous = 0.0, 0.0, points[0]
    while t < 1.0:
        a = 1 - t
        weights = (a * a * a, (3 * t) * (a * a), (3 * (t * t)) * a, t * t * t)
        current = tuple(points[0][i] * weights[0] + weights[1] * points[1][i] + weights[2] * points[2][i]
                        + weights[3] * points[3][i] for i in (0, 1))  # fmt: skip
        if t > 0:
            x, y = (current[i] - previous[i] for i in (0, 1))
            length += math.sqrt(x * x + y * y)
        previous, t = current, t + 1.0 / STEPS
    return angle, length


def segment_findings(angle: float, length: float, horizontal: tuple, vertical: tuple) -> list[tuple]:
    result = []
    for target in (0, 180, 90, -90):
        if angle != target and target - ANGLE < angle < target + ANGLE:
            result.append(("angle", angle, target))
    for label, stems, axes in (("horizontal stem", horizontal, (0, 180)), ("vertical stem", vertical, (90, -90))):
        if length in stems:
            continue
        if any(axis - ANGLE < angle < axis + ANGLE for axis in axes):
            for stem in stems:
                if length != stem and stem * (1 - STEM) < length < stem * (1 + STEM):
                    result.append((label, length, stem))
    return result


def plan_near(layer: Any, options: Mapping[str, Any], context: Context) -> list[Issue]:
    if context.measures is None:
        raise ValueError("Master metrics are unavailable.")
    metrics, horizontal, vertical = context.measures(context.master)
    rows = []
    for number, nodes, closed in own_paths(layer):
        if any(off for *_, off in nodes) and _is_tt(layer, number):
            raise ValueError(TT_ERROR)
        path = nodes[1:] + nodes[:1] if closed else nodes
        for index, segment in enumerate(segments(path)):
            for kind, actual, target in segment_findings(*measure(segment), horizontal, vertical):
                rows.append(_finding(number, "segment", index, kind, actual, target, None))
        for index, (x, y, _) in enumerate(path):
            checks = (("x zero", x, 0), ("y zero", y, 0),
                      *zip(("ascender", "cap height", "x height", "descender"), (y,) * 4, metrics, strict=True))  # fmt: skip
            for label, actual, target in checks:
                if actual != target and target - METRIC < actual < target + METRIC:
                    stored = (index + 1) % len(nodes) if closed else index
                    rows.append(_finding(number, "node", index, "node " + label, actual, target, stored))
    return rows


def _is_tt(layer: Any, number: int) -> bool:
    own = [c for s in layer.shapes if not s.isComponent for c in s.contours]
    return bool(own[number].isTT)


def _finding(number: int, part: str, index: int, kind: str, actual: float, target: float, stored: int | None) -> Issue:
    marks = ((number, stored),) if stored is not None else ()
    return Issue(f"path {number + 1}, {part} {index + 1}", kind, f"{actual:g} → {target:g}?", marks=marks)


# Dangerous Offcurves -----------------------------------------------------------
def curves(path: list[tuple[float, float, bool]]) -> list[tuple[tuple, int]]:
    """First-offcurve windows with the original unconditional neighbour wrap."""
    result = []
    for i, node in enumerate(path):
        if node[2] and not path[i - 1][2]:
            window = (path[i - 1], node, path[(i + 1) % len(path)], path[(i + 2) % len(path)])
            result.append((tuple(n[:2] for n in window), i))
    return result


def _intersections(curve: tuple, line: tuple) -> Any:
    from fontTools.misc.bezierTools import curveLineIntersections

    return curveLineIntersections(curve, line)


def axis_hits(curve: tuple, control: tuple, axis: int) -> tuple:
    coordinates = tuple(point[axis] for point in curve)
    if min(coordinates) > PROBE or max(coordinates) < -PROBE:
        return ()
    x, y = control
    line = ((-PROBE, y), (PROBE, y)) if axis == 0 else ((x, -PROBE), (x, PROBE))
    try:
        values = _intersections(curve, line)
    except (ArithmeticError, ValueError):
        values = []
    fixed = 1 - axis
    if all(point[fixed] == control[fixed] for point in curve):
        return ()
    result = [(hit.t1, tuple(hit.pt)) for hit in values if 0 < hit.t1 < 1 and 0 <= hit.t2 <= 1]
    for t, point in ((0, curve[0]), (1, curve[-1])):
        if point[fixed] == control[fixed] and -PROBE <= point[axis] <= PROBE:
            result.append((t, point))
    return tuple(sorted(result, key=lambda hit: hit[0]))


def dangerous(curve: tuple, threshold: float = THRESHOLD) -> bool:
    b, c = curve[1:3]
    hits = (axis_hits(curve, b, 0), axis_hits(curve, b, 1), axis_hits(curve, c, 0), axis_hits(curve, c, 1))
    if not all(hits):
        return False
    points = tuple(row[0][1] for row in hits)
    return any(d < threshold for d in (abs(points[0][0] - b[0]), abs(points[1][1] - b[1]),
                                       abs(points[2][0] - c[0]), abs(points[3][1] - c[1])))  # fmt: skip


def plan_dangerous(layer: Any, options: Mapping[str, Any], context: Context) -> list[Issue]:
    threshold = float(options.get("threshold", THRESHOLD))
    if not math.isfinite(threshold):
        raise ValueError("The threshold must be finite.")
    rows = []
    for number, nodes, _ in own_paths(layer):
        for curve, index in curves(nodes):
            if any(not math.isfinite(v) for p in curve for v in p):
                raise ValueError("Cubic coordinates must be finite and the axis horizontal or vertical.")
            if dangerous(curve, threshold):
                rows.append(Issue(f"contour {number + 1}", f"handle {index + 1}", f"closer than {threshold:g}",
                                  marks=((number, index), (number, (index + 1) % len(nodes)))))  # fmt: skip
    return rows
