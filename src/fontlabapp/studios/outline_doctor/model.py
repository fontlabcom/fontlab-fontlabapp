# this_file: src/fontlabapp/studios/outline_doctor/model.py
# SPDX-License-Identifier: Apache-2.0
"""Outline Doctor data types and the shared native-outline helpers.

What: ``Option`` (one control of a check), ``Issue`` (one planned or reported
row, with its native edit payload, its compatibility key, the after-geometry
for the ghost and the points to highlight), ``Context`` (what a planner may
read besides its layer) and ``Check`` (one registry entry: detect, fix and
verify). The helpers port ``fontlabapp.contours.writer``: editable outline
shapes, plain translations, node points, area and the compatibility hold-back.
Why: the studio boundary forbids ``fontlabapp.contours``; ``fixes`` and
``reports`` share these, and ``session`` drives every ``Check`` the same way.
"""

import math
from collections.abc import Callable, Mapping, Sequence
from typing import Any, NamedTuple

import fontlabapp.core.sharing as sharing

EPSILON = 1e-9
Point = tuple[float, float, bool]
MIXED = "masters would differ, kept"
OUTSIDE = "other masters need it too; choose All masters"


class Option(NamedTuple):
    """One numeric spin box ("spin") or tick box ("tick") a check reads."""

    key: str
    label: str
    kind: str
    default: float | bool
    low: float = 0
    high: float = 0
    decimals: int = 0
    suffix: str = ""


class Issue(NamedTuple):
    """One row: ``edit`` is the native payload (None for a report or a note).

    ``key`` is compared across masters by the compatibility guard; ``after``
    maps (shape position, contour index) to glyph-space (x, y, on) points, or
    None for a deleted contour; ``marks`` are TGlyph ``(contour, index)`` keys.
    """

    name: str
    old: str
    new: str
    edit: Any = None
    problem: str = ""
    key: tuple | int | None = None
    after: tuple = ()
    marks: tuple = ()


class Context(NamedTuple):
    """Read-only facts a planner may need beside its layer."""

    glyph: str
    master: str
    reference: Any = None
    measures: Callable[[str], tuple] | None = None


Planner = Callable[[Any, Mapping[str, Any], Context], list[Issue]]
Writer = Callable[[Any, list[Any], Mapping[str, Any]], None]
Verifier = Callable[[Any, list[Any]], list[str]]


class Check(NamedTuple):
    """One registry entry. ``scope`` is the default: "current" or "all" masters.

    ``bases`` offers the shared Scriptmix panel's "Also edit bases of automatic
    composites" consent (off by default; every fix's original showed it).
    ``advise`` returns save-risk advice read after a successful write; it is
    appended to the status and never counts as a failed store.
    """

    key: str
    title: str
    tab: str
    action: str
    source: str
    plan: Planner
    write: Writer | None = None
    verify: Verifier | None = None
    structural: bool = False
    scope: str = "current"
    options: tuple[Option, ...] = ()
    whole_font: bool = False
    columns: tuple[str, str, str] = ("Item", "Now", "After")
    bases: bool = False
    advise: Verifier | None = None

    @property
    def report(self) -> bool:
        return self.write is None

    def defaults(self) -> dict[str, Any]:
        return {option.key: option.default for option in self.options}


# Native outline helpers (port of fontlabapp.contours.writer) -----------------
def plural(count: int, word: str) -> str:
    return f"{count} {word}" + ("" if count == 1 else "s")


def fmt(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def translation(shape: Any) -> tuple[float, float] | None:
    """(dx, dy) when the shape transform only moves; None for scale, slant or turn."""
    matrix = shape.transform
    if matrix is None:
        return (0.0, 0.0)
    plain = (
        abs(matrix.m11() - 1) < EPSILON
        and abs(matrix.m22() - 1) < EPSILON
        and abs(matrix.m12()) < EPSILON
        and abs(matrix.m21()) < EPSILON
    )
    return (float(matrix.dx()), float(matrix.dy())) if plain else None


def outline_shapes(layer: Any) -> tuple[list[tuple[int, Any]], list[str]]:
    """(position, shape) of the editable own outlines and notes for the rest."""
    shapes, notes = [], []
    for position, shape in enumerate(layer.shapes):
        if shape.isComponent or not list(shape.contours):
            continue
        if sharing.element_shared(shape, layer):
            notes.append("shared outline, kept")
        elif translation(shape) is None:
            notes.append("scaled or rotated shape, kept")
        else:
            shapes.append((position, shape))
    return shapes, notes


def contours(layer: Any) -> list[tuple[int, int, int, Any, Any]]:
    """(number, position, index, shape, contour) over the editable outlines; numbers count from 1."""
    found, number = [], 0
    for position, shape in outline_shapes(layer)[0]:
        for index, contour in enumerate(shape.contours):
            number += 1
            found.append((number, position, index, shape, contour))
    return found


def note_rows(notes: Sequence[str]) -> list[Issue]:
    counts: dict[str, int] = {}
    for note in notes:
        counts[note] = counts.get(note, 0) + 1
    return [Issue(plural(count, "shape"), "", note) for note, count in counts.items()]


def node_points(contour: Any) -> list[Point]:
    """(x, y, on-curve) of every node, in stored order and shape coordinates."""
    return [(float(n.x), float(n.y), bool(n.isOn())) for n in contour.nodes()]


def moved(points: Sequence[Point], shape: Any) -> tuple[Point, ...]:
    """``points`` in glyph coordinates (plain-translated shapes only)."""
    dx, dy = translation(shape) or (0.0, 0.0)
    return tuple((x + dx, y + dy, on) for x, y, on in points)


def after(position: int, index: int, points: Sequence[Point] | None, shape: Any) -> tuple:
    """One ``Issue.after`` entry: deleted (None) or replaced by ``points``."""
    return (((position, index), None if points is None else moved(points, shape)),)


def segments_of(points: Sequence[Point], truetype: bool) -> tuple[tuple[tuple[float, float], ...], ...]:
    """Closed line/cubic/quadratic segments starting at the first on-curve node."""
    points = list(points)
    start = next((i for i, p in enumerate(points) if p[2]), None)
    if start is None:
        return ()
    ring = points[start + 1 :] + points[: start + 1]
    current = points[start][:2]
    result, controls = [], []
    for x, y, on in ring:
        if not on:
            controls.append((x, y))
            continue
        end = (x, y)
        if not controls:
            result.append((current, end))
        elif not truetype and len(controls) == 2:
            result.append((current, controls[0], controls[1], end))
        else:
            for a, b in zip(controls, controls[1:], strict=False):
                middle = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                result.append((current, a, middle))
                current = middle
            result.append((current, controls[-1], end))
        current, controls = end, []
    return tuple(result)


def unsigned_area(segments: Sequence[tuple[tuple[float, float], ...]]) -> float:
    """Exact area of closed line/quadratic/cubic segments (Green's theorem)."""
    total = 0.0
    for segment in segments:
        if any(not math.isfinite(v) for point in segment for v in point):
            raise ValueError("Contour coordinates must be finite.")
        if len(segment) == 2:
            (x0, y0), (x1, y1) = segment
            total += (x0 * y1 - x1 * y0) / 2
        elif len(segment) == 3:
            total += _quad(segment)
        elif len(segment) == 4:
            total += _cubic(segment)
        else:
            raise ValueError("Contour segments must be continuous lines or Beziers.")
    return abs(total)


def _quad(segment: tuple) -> float:
    (x0, y0), (x1, y1), (x2, y2) = segment
    return (x0 * (2 * y1 + y2) - y0 * (2 * x1 + x2) + 2 * (x1 * y2 - y1 * x2)) / 6


def _cubic(segment: tuple) -> float:
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = segment
    return (
        x0 * (6 * y1 + 3 * y2 + y3)
        + 3 * x1 * (-2 * y0 + y2 + y3)
        + 3 * x2 * (-y0 - y1 + 2 * y3)
        - x3 * (y0 + 3 * y1 + 6 * y2)
    ) / 20


def held_back(planned: Mapping[str, list[Issue]], chosen: Sequence[str]) -> str:
    """The compatibility hold-back reason for one glyph, or "" when the edit may go ahead.

    ``planned`` maps every master to its issues. Masters must plan the same
    keys; a master outside ``chosen`` that needs the edit holds it back too.
    """
    keys = {master: tuple(issue.key for issue in issues if issue.edit is not None and issue.key is not None)
            for master, issues in planned.items()}  # fmt: skip
    if not any(keys.values()):
        return ""
    if len(set(keys.values())) > 1:
        return MIXED
    if any(keys[master] and master not in chosen for master in keys):
        return OUTSIDE
    return ""
