# this_file: src/fontlabapp/contours/dangerous_offcurves/model.py
# SPDX-License-Identifier: Apache-2.0
"""Slobzheninov's complete offcurve probe policy with an explicit analytic backend.

All four finite probes and the strict threshold survive. Ascending curve t
explicitly adapts unspecified Glyphs ordering; engine equivalence remains
unproved. See NOTICE.
"""

from dataclasses import dataclass
from math import isfinite
from time import monotonic
from typing import Any

THRESHOLD = 0.05
PROBE = 10000
KEY = "dangerous-offcurves"
Point = tuple[float, float]
Curve = tuple[Point, Point, Point, Point]


@dataclass(frozen=True)
class Node:
    """A layer-coordinate point and exact control/on-curve role."""

    x: float
    y: float
    off: bool


@dataclass(frozen=True)
class Layer:
    """One full-font layer in stored order, with detached own-path nodes."""

    identity: tuple[int, int]
    glyph: str
    name: str
    paths: tuple[tuple[Node, ...], ...]


@dataclass(frozen=True)
class Report:
    """Distinct winning layer identities and every original per-curve log row."""

    layers: tuple[tuple[int, int], ...]
    hits: tuple[tuple[str, str], ...]
    threshold: float


def check(deadline: float) -> None:
    """Check one absolute budget; never return a partial font prefix."""
    if monotonic() >= deadline:
        raise TimeoutError(
            "Dangerous Offcurves exceeded its deadline; no partial result."
        )


def curves(
    path: tuple[Node, ...], *, deadline: float = float("inf")
) -> tuple[Curve, ...]:
    """Reproduce first-offcurve windows and Glyphs' unconditional neighbour wrap.

    This retains the source's four-point call even for quadratic/malformed
    neighbourhoods; it does not silently reinterpret or discard such windows.
    """
    result = []
    for i, node in enumerate(path):
        check(deadline)
        if node.off and not path[i - 1].off:
            window = (
                path[i - 1],
                node,
                path[(i + 1) % len(path)],
                path[(i + 2) % len(path)],
            )
            result.append(tuple((n.x, n.y) for n in window))
    return tuple(result)


def _intersections(curve: Curve, line: tuple[Point, Point]) -> Any:
    """Load the existing optional fontui/fontTools dependency only when requested."""
    from fontTools.misc.bezierTools import curveLineIntersections

    return curveLineIntersections(curve, line)


def axis_hits(
    curve: Curve, control: Point, axis: int, *, deadline: float = float("inf")
) -> tuple:
    """Return analytic finite-probe hits in deterministic ascending curve time.

    fontTools can return hits outside the supplied line's parameter domain;
    filter t2 explicitly. Coincident-axis projections return its empty root set.
    Numeric solver errors retain the source helper's no-intersection outcome.
    """
    check(deadline)
    if (
        axis not in (0, 1)
        or len(curve) != 4
        or any(not isfinite(v) for p in curve for v in p)
    ):
        raise ValueError(
            "Cubic coordinates must be finite and the axis horizontal or vertical."
        )
    # Nonnegative Bernstein weights keep the curve inside its control hull.
    # Strict comparisons preserve hits at the exact finite probe endpoints.
    coordinates = tuple(point[axis] for point in curve)
    if min(coordinates) > PROBE or max(coordinates) < -PROBE:
        return ()
    x, y = control
    line = ((-PROBE, y), (PROBE, y)) if axis == 0 else ((x, -PROBE), (x, PROBE))
    try:
        values = _intersections(curve, line)
    except (ArithmeticError, ValueError):
        values = []
    check(deadline)
    fixed = 1 - axis
    if all(point[fixed] == control[fixed] for point in curve):
        return ()  # The backend represents coincident projections by no discrete roots.
    result = [
        (hit.t1, tuple(hit.pt))
        for hit in values
        if 0 < hit.t1 < 1 and 0 <= hit.t2 <= 1
    ]
    # Discard numerical endpoint hits: alignment can round outside points onto
    # the finite line. Restore only exact endpoint/control coordinate equalities
    # within the source bounds; do not clamp roots or widen thresholds.
    for t, point in ((0, curve[0]), (1, curve[-1])):
        if (
            point[fixed] == control[fixed]
            and -PROBE <= point[axis] <= PROBE
        ):
            result.append((t, point))
    return tuple(sorted(result, key=lambda hit: hit[0]))


def dangerous(
    curve: Curve, threshold: float = THRESHOLD, *, deadline: float = float("inf")
) -> bool:
    """Keep all-four-hit gating and any strict componentwise distance test."""
    b, c = curve[1:3]
    hits = (
        axis_hits(curve, b, 0, deadline=deadline),
        axis_hits(curve, b, 1, deadline=deadline),
        axis_hits(curve, c, 0, deadline=deadline),
        axis_hits(curve, c, 1, deadline=deadline),
    )
    if not all(hits):
        return False
    points = tuple(row[0][1] for row in hits)
    return any(
        distance < threshold
        for distance in (
            abs(points[0][0] - b[0]),
            abs(points[1][1] - b[1]),
            abs(points[2][0] - c[0]),
            abs(points[3][1] - c[1]),
        )
    )


def analyse(
    layers: tuple[Layer, ...],
    threshold: float = THRESHOLD,
    *,
    deadline: float = float("inf"),
) -> Report:
    """Scan every original candidate and keep layer identity order without repeats."""
    if not isfinite(threshold):
        raise ValueError("The threshold must be finite.")
    winners, hits = [], []
    for layer in layers:
        check(deadline)
        for path in layer.paths:
            for curve in curves(path, deadline=deadline):
                check(deadline)
                if dangerous(curve, threshold, deadline=deadline):
                    if layer.identity not in winners:
                        winners.append(layer.identity)
                    hits.append((layer.glyph, layer.name))
    check(deadline)
    return Report(tuple(winners), tuple(hits), threshold)


def render(report: Report) -> str:
    """Keep original finding rows or the complete no-problem diagnosis."""
    if report.hits:
        return "".join(f"{glyph} -- {layer}\n" for glyph, layer in report.hits)
    return (
        "Could not find any offcurve points that are closer to their curves "
        f"than {report.threshold} units"
    )


def show() -> Any:
    """Run the full real-tab workflow and retain its complete owned result text."""
    from fontlabapp.contours.dangerous_offcurves.ui import dialog_type
    from fontlabapp.core.scripting import show_script_dialog

    return show_script_dialog(dialog_type(), KEY)
