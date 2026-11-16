# this_file: src/fontlabapp/contours/near_miss/model.py
# SPDX-License-Identifier: MIT AND Apache-2.0
"""Complete Close But No Cigar diagnostics, adapted from Simon Cozens; see NOTICE.

Keep strict ±2 degree/position and ±5% length tests, exact exclusions, duplicate
stem/metric reports, occurrence order and glyphmonkey's open-path wrap. Repair
its cubic angle method/property mismatch; retain its sub-one sampling endpoint.
"""

from dataclasses import dataclass
from math import atan2, degrees, isfinite, sqrt
from time import monotonic
from typing import Any


@dataclass(frozen=True)
class Node:
    """One own-path node in Glyphs order, including off-curve handles."""

    point: tuple[float, float]
    off: bool


@dataclass(frozen=True)
class Glyph:
    """One selected occurrence's first layer and its associated master data."""

    name: str
    layer: str
    master: str
    metrics: tuple[float, float, float, float]
    horizontal: tuple[float, ...]
    vertical: tuple[float, ...]
    paths: tuple[tuple[Node, ...], ...]


@dataclass(frozen=True)
class Finding:
    """One original ordered message, retaining its exact source location."""

    glyph: str
    layer: str
    master: str
    path: int
    index: int
    kind: str
    actual: float
    target: float


def number(value: Any) -> float:
    """Refuse unreadable/nonfinite values instead of silently dropping checks."""
    if type(value) not in (int, float) or not isfinite(value):
        raise ValueError("Expected a finite native number.")
    return value


def segments(nodes: tuple[Node, ...]) -> tuple:
    """Preserve glyphmonkey's last-to-first start even for open paths."""
    if not nodes:
        return ()
    result, pending = [], [nodes[-1].point]
    for node in nodes:
        pending.append(node.point)
        if not node.off:
            if len(pending) not in (2, 4):
                raise ValueError("Only line or cubic topology is supported.")
            result.append(tuple(pending))
            pending = [node.point]
    return tuple(result)


def measure(points: tuple) -> tuple[float, float]:
    """Use endpoint angle and line chord or original 50-step cubic length."""
    if len(points) not in (2, 4):
        raise ValueError("Expected a line or cubic segment.")
    for point in points:
        for value in point:
            number(value)
    dx, dy = (points[-1][i] - points[0][i] for i in (0, 1))
    angle = degrees(atan2(dy, dx))
    if len(points) == 2:
        return angle, sqrt(dx * dx + dy * dy)
    t, length, previous = 0.0, 0.0, points[0]
    while t < 1.0:
        a = 1 - t
        weights = (a * a * a, (3 * t) * (a * a), (3 * (t * t)) * a, (t * t * t))
        # Keep upstream operation association: exact stem equality is observable.
        current = tuple(
            points[0][i] * weights[0]
            + weights[1] * points[1][i]
            + weights[2] * points[2][i]
            + weights[3] * points[3][i]
            for i in (0, 1)
        )
        if t > 0:
            x, y = (current[i] - previous[i] for i in (0, 1))
            length += sqrt(x * x + y * y)
        previous, t = current, t + 1.0 / 50
    return angle, length


def segment_findings(
    angle: float, length: float, horizontal: tuple, vertical: tuple
) -> tuple:
    """Keep exact stem suppression before orientation/relative comparisons."""
    result = []
    for target in (0, 180, 90, -90):
        if angle != target and target - 2 < angle < target + 2:
            result.append(("angle", angle, target))
    for label, stems, axes in (
        ("horizontal stem", horizontal, (0, 180)),
        ("vertical stem", vertical, (90, -90)),
    ):
        if length in stems:
            continue
        if any(axis - 2 < angle < axis + 2 for axis in axes):
            for stem in stems:
                if length != stem and stem * (1 - 0.05) < length < stem * (1 + 0.05):
                    result.append((label, length, stem))
    return tuple(result)


def findings(
    rows: tuple[Glyph, ...], deadline: float | None = None
) -> tuple[Finding, ...]:
    """Report all segment checks followed by all six node checks per path."""
    result = []
    for row in rows:
        if deadline is not None and monotonic() >= deadline:
            raise TimeoutError("Near-miss analysis expired; no partial report.")
        if len(row.metrics) != 4:
            raise ValueError("Expected all four associated-master metrics.")
        for value in (*row.metrics, *row.horizontal, *row.vertical):
            number(value)
        for path_index, path in enumerate(row.paths):
            if deadline is not None and monotonic() >= deadline:
                raise TimeoutError("Near-miss analysis expired; no partial report.")
            for node in path:
                if deadline is not None and monotonic() >= deadline:
                    raise TimeoutError("Near-miss analysis expired; no partial report.")
                if len(node.point) != 2 or type(node.off) is not bool:
                    raise ValueError("Unreadable native node coordinates/role.")
                for coordinate in node.point:
                    number(coordinate)
            for index, segment in enumerate(segments(path)):
                if deadline is not None and monotonic() >= deadline:
                    raise TimeoutError("Near-miss analysis expired; no partial report.")
                angle, length = measure(segment)
                for kind, actual, target in segment_findings(
                    angle, length, row.horizontal, row.vertical
                ):
                    result.append(
                        Finding(
                            row.name,
                            row.layer,
                            row.master,
                            path_index,
                            index,
                            kind,
                            actual,
                            target,
                        )
                    )
            for index, node in enumerate(path):
                if deadline is not None and monotonic() >= deadline:
                    raise TimeoutError("Near-miss analysis expired; no partial report.")
                x, y = node.point
                checks = (
                    ("x zero", x, 0),
                    ("y zero", y, 0),
                    *zip(
                        ("ascender", "cap height", "x height", "descender"),
                        (y,) * 4,
                        row.metrics,
                    ),
                )
                for label, actual, target in checks:
                    if actual != target and target - 2 < actual < target + 2:
                        result.append(
                            Finding(
                                row.name,
                                row.layer,
                                row.master,
                                path_index,
                                index,
                                "node " + label,
                                actual,
                                target,
                            )
                        )
    if deadline is not None and monotonic() >= deadline:
        raise TimeoutError("Near-miss analysis expired; no partial report.")
    return tuple(result)


def render(rows: tuple[Glyph, ...]) -> str:
    """Render a complete selectable report without touching the Output panel."""
    if not rows:
        raise ValueError("Select glyphs before running Close But No Cigar.")
    deadline = monotonic() + 2.0
    hits = findings(rows, deadline)
    lines = [
        f"Close But No Cigar — {len(rows)} selected glyph occurrences",
        "First layer only; associated-master stems and metrics. No font changes.",
    ]
    for hit in hits:
        if monotonic() >= deadline:
            raise TimeoutError("Near-miss rendering expired; no partial report.")
        lines.append(
            f"{hit.glyph} / {hit.layer} / {hit.master} — path {hit.path + 1}, {'node' if hit.kind.startswith('node') else 'segment'} {hit.index + 1}: {hit.kind}: {hit.actual} → {hit.target}?"
        )
    lines.append(f"{len(hits)} near misses." if hits else "No near misses.")
    if monotonic() >= deadline:
        raise TimeoutError("Near-miss rendering expired; no partial report.")
    return "\n".join(lines)


def show() -> Any:
    """Open the shared owned Refresh/Close snapshot panel lazily."""
    from fontlabapp.contours.near_miss.ui import NearMissDialog
    from fontlabapp.core.scripting import show_script_dialog

    return show_script_dialog(NearMissDialog, NearMissDialog.KEY)
