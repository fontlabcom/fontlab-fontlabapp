# this_file: src/fontlabapp/studios/anchor_studio/model.py
# SPDX-License-Identifier: Apache-2.0
"""Anchor Studio maths: Qt-free planners, safety checks and the read-back check.

What: A layer's anchors are read once into ``Pin`` tuples (name, x, y). Every
planner turns those pins (plus the layer's ink box and advance) into
``Change`` rows; a ``Change`` with an ``edit`` is written, one with a
``problem`` is shown and refused. Edits are ``("set", name, (x, y))`` (add the
anchor or move the only anchor of that name), ``("remove", index)`` and
``("rename", index, new)`` where ``index`` is the pin's place in the snapshot.
``verify`` compares the stored anchors with the planned result within
``TOLERANCE`` and names every sub-unit move that FontLab rounded to no change
(Scriptmix TODO:78), so the studio reports it instead of claiming success.
Why: The planners reproduce the Scriptmix ``Scripts/Anchors`` tools; keeping
them free of Qt and FontLab makes every rule unit-testable.
Used by ``fontlabapp.studios.anchor_studio.session`` and ``.tabs``.
"""

import re
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from math import ceil, floor, isfinite, radians, tan
from time import monotonic
from typing import Any, NamedTuple

EPSILON = 1e-6
TOLERANCE = 0.5
STACK_DISTANCE = 1.0
OPTICAL_BUDGET = 1.5
MAX_COLUMNS = 512
HANDLE_SIZES = (5, 8, 12)
ORIGIN_ERROR = "FontLab cannot restore an existing anchor moved to 0, 0 with Redo; move it elsewhere."
DUPLICATE_ERROR = "{names} used more than once on this layer; use Clean-up > Find duplicates first."
APPEARANCE = {
    "top": 5, "_bottom": 5, "bottom": 6, "_top": 6, "left": 7, "_left": 7,
    "right": 8, "_right": 8, "center": 1, "_center": 1,
}  # fmt: skip
"""Name-derived pin appearance of a new anchor (FontLab ``flPinPoint`` detectAppearance)."""

BOUNDS_ANCHORS = (("top", "top", True), ("bottom", "bottom", True), ("_top", "bottom", False), ("_bottom", "top", False))
REFERENCES = (("Advance width", "advance"), ("Ink box", "ink"))
METRICS = (("Baseline", None), ("x-height", "xHeight"), ("Cap height", "capsHeight"),
           ("Ascender", "ascender"), ("Descender", "descender"))  # fmt: skip
OPPOSITES = (("_top", "bottom"), ("_bottom", "top"))

Box = tuple[float, float, float, float]
Edit = tuple[Any, ...]


class Pin(NamedTuple):
    """One anchor of a layer snapshot."""

    name: str
    x: float
    y: float


class Change(NamedTuple):
    """One planned row: ``edit`` is written; ``problem`` refuses the whole layer."""

    name: str
    old: str
    new: str
    edit: Edit | None = None
    problem: str = ""


class Facts(NamedTuple):
    """What a planner may read of one layer: its pins, ink box and advance."""

    pins: tuple[Pin, ...]
    box: Box | None
    advance: float


Planner = Callable[[str, Facts, Any, str], "list[Change] | str"]


class OverlayPoint(NamedTuple):
    """Duck-typed TGlyph overlay point (``x``, ``y``, ``type``, ``on_curve``)."""

    x: float
    y: float
    type: str | None = "line"
    smooth: bool = False

    @property
    def on_curve(self) -> bool:
        return self.type is not None


class OverlayContour(NamedTuple):
    points: tuple[OverlayPoint, ...]
    closed: bool = True


class Overlay(NamedTuple):
    """Duck-typed TGlyph overlay: only ``contours`` is drawn."""

    contours: tuple[OverlayContour, ...]
    components: tuple = ()
    anchors: tuple = ()


# Formatting --------------------------------------------------------------
def half_up(value: float) -> int:
    return int(floor(value + 0.5))


def fmt(value: float) -> str:
    return f"{value:g}"


def point_text(x: float, y: float) -> str:
    return f"{fmt(x)}, {fmt(y)}"


def subject(names: Sequence[str]) -> str:
    """Undo-label subject: the glyph name, or ``"N glyphs"`` for several."""
    unique = list(dict.fromkeys(names))
    return unique[0] if len(unique) == 1 else f"{len(unique)} glyphs"


def parse_names(text: str) -> list[str]:
    """Anchor names typed with commas, semicolons or spaces, in order, once each."""
    return list(dict.fromkeys(part for part in re.split(r"[,;\s]+", text or "") if part))


# Safety ------------------------------------------------------------------
def duplicated(pins: Iterable[Pin], names: Iterable[str] | None = None) -> list[str]:
    """Names carried by several pins (limited to ``names`` when given)."""
    counts = Counter(pin.name for pin in pins)
    wanted = None if names is None else set(names)
    return sorted(name for name, count in counts.items() if count > 1 and (wanted is None or name in wanted))


def refusal(names: Sequence[str]) -> list[Change]:
    return [Change(", ".join(names), "", "", None, DUPLICATE_ERROR.format(names=", ".join(names)))]


def setter(pins: Sequence[Pin], name: str, x: float, y: float) -> Change | None:
    """The ``set`` change for ``name`` at (x, y); None when nothing moves."""
    old = next((pin for pin in pins if pin.name == name), None)
    if old is None:
        return Change(name, "–", point_text(x, y), ("set", name, (x, y)))
    if abs(old.x - x) <= EPSILON and abs(old.y - y) <= EPSILON:
        return None
    if abs(x) <= EPSILON and abs(y) <= EPSILON:
        return Change(name, point_text(old.x, old.y), "0, 0", None, ORIGIN_ERROR)
    return Change(name, point_text(old.x, old.y), point_text(x, y), ("set", name, (x, y)))


def _sets(pins: Sequence[Pin], names: Sequence[str], targets: Callable[[Pin | None, str], tuple[float, float] | None],
          *, add: bool = False) -> list[Change]:  # fmt: skip
    clash = duplicated(pins, names)
    if clash:
        return refusal(clash)
    changes = []
    for name in names:
        old = next((pin for pin in pins if pin.name == name), None)
        if old is None and not add:
            continue
        target = targets(old, name)
        change = None if target is None else setter(pins, name, *target)
        if change is not None:
            changes.append(change)
    return changes


# Place -------------------------------------------------------------------
def target_point(box: Box, edge: str, offset: float) -> tuple[int, int]:
    """Centre of the box on ``edge`` ("top"/"bottom"), pushed out by ``offset``."""
    xmin, ymin, xmax, ymax = box
    y = ymax + offset if edge == "top" else ymin - offset
    return half_up((xmin + xmax) / 2), half_up(y)


def bounds_changes(facts: Facts, wanted: Sequence[tuple[str, str, float]]) -> list[Change] | str:
    """Place From Bounds: add or move each ``(name, edge, offset)`` anchor from the ink box."""
    if facts.box is None:
        return "empty layer, skipped"
    edges = {name: (edge, offset) for name, edge, offset in wanted}
    return _sets(facts.pins, list(edges), lambda old, name: target_point(facts.box, *edges[name]), add=True)  # type: ignore[arg-type]


# Align -------------------------------------------------------------------
def target_x(facts: Facts, reference: str, fraction: float, angle: float, y: float) -> float | None:
    """X on the reference line at height ``y``; None for an empty ink box.

    ``fraction`` 0 is the left edge, 1 the right edge. ``angle`` is the FontLab
    italic angle in degrees; the line leans right when it is negative. The
    advance line passes through the baseline, the ink line through the box centre.
    """
    slope = -tan(radians(angle))
    if reference == "advance":
        return facts.advance * fraction + slope * y
    if facts.box is None:
        return None
    xmin, ymin, xmax, ymax = facts.box
    return xmin + (xmax - xmin) * fraction + slope * (y - (ymin + ymax) / 2)


def centre_changes(facts: Facts, names: Sequence[str], reference: str, fraction: float, angle: float) -> list[Change]:
    """Center Horizontally: move the named anchors sideways; y never changes."""

    def target(old: Pin | None, name: str) -> tuple[float, float] | None:
        x = target_x(facts, reference, fraction, angle, old.y)  # type: ignore[union-attr]
        return None if x is None else (half_up(x), old.y)  # type: ignore[union-attr]

    return _sets(facts.pins, names, target)


def metric_value(metrics: Any, attribute: str | None) -> int:
    """A master's metric in font units; ``None`` is the baseline, 0."""
    return 0 if attribute is None else half_up(float(getattr(metrics, attribute)))


def snap_changes(facts: Facts, names: Sequence[str], y: float) -> list[Change]:
    """Snap To Metrics: move the named anchors vertically to ``y``."""
    return _sets(facts.pins, names, lambda old, name: (old.x, y))  # type: ignore[union-attr]


def snap(value: float, step: int) -> int:
    """Nearest multiple of ``step``, halves upward: 15→20, −15→−10."""
    return int(step * floor(value / step + 0.5))


def round_changes(facts: Facts, step: int, do_x: bool, do_y: bool, names: Sequence[str]) -> list[Change]:
    """Round To Grid: snap the named anchors (every anchor when ``names`` is empty)."""
    if step < 1:
        raise ValueError("The grid step must be at least 1.")
    if not (do_x or do_y):
        raise ValueError("Tick x, y or both.")
    chosen = list(names) or list(dict.fromkeys(pin.name for pin in facts.pins))

    def target(old: Pin | None, name: str) -> tuple[float, float]:
        return (snap(old.x, step) if do_x else old.x, snap(old.y, step) if do_y else old.y)  # type: ignore[union-attr]

    return _sets(facts.pins, chosen, target)


# Optical centre (behaviour rewrite of Simon Cozens' GlyphsScripts tool, MIT 2017) ------
Ring = Sequence[tuple[float, float]]


def optical_position(strips: Sequence[tuple[float, float]], left: float, right: float) -> float:
    """Ink-weighted median column, moved one third of the way from the box centre."""
    total = sum(weight for _, weight in strips)
    if total <= 0:
        raise ValueError("No closed ink was found.")
    running = 0.0
    for position, weight in strips:
        running += weight
        if running > total / 2:
            centre = (left + right) / 2
            return centre + (position - centre) / 3
    raise ValueError("No ink median was found.")  # pragma: no cover - running reaches total


def column_weight(rings: Sequence[Ring], x: float, deadline: float) -> float:
    """Filled length of the vertical line at ``x`` under the nonzero winding rule."""
    crossings: list[tuple[float, int]] = []
    for ring in rings:
        if monotonic() > deadline:
            raise TimeoutError("Optical centre layer time budget exceeded.")
        for (ax, ay), (bx, by) in zip(ring, [*ring[1:], ring[0]]):
            if min(ax, bx) <= x < max(ax, bx):
                crossings.append((ay + (x - ax) * (by - ay) / (bx - ax), 1 if bx > ax else -1))
    crossings.sort()
    filled, winding, start = 0.0, 0, 0.0
    for y, direction in crossings:
        if winding == 0:
            start = y
        winding += direction
        if winding == 0:
            filled += y - start
    return filled


def estimate_rings(rings: Sequence[Ring], deadline: float) -> int:
    """Optical x of closed rings, sampled in at most ``MAX_COLUMNS`` columns."""
    xs = [x for ring in rings for x, _ in ring]
    if not xs or not all(isfinite(v) for ring in rings for point in ring for v in point):
        raise ValueError("No finite closed ink was found.")
    left, right = min(xs), max(xs)
    width = right - left
    if width <= 0:
        raise ValueError("No closed ink was found.")
    count = max(1, min(MAX_COLUMNS, ceil(width)))
    step = width / count
    strips = []
    for column in range(count):
        x = left + (column + 0.5) * step
        strips.append((x, column_weight(rings, x, deadline)))
    return half_up(optical_position(strips, left, right))


def optical_changes(facts: Facts, estimate: int | str) -> list[Change]:
    """Optical Center: report the optical x; align the x of an existing ``top`` anchor."""
    if isinstance(estimate, str):
        return [Change("optical x", "", f"{estimate}; layer skipped", None, "")]
    report = Change("optical x", "", str(estimate))
    tops = [pin for pin in facts.pins if pin.name == "top"]
    if len(tops) > 1:
        return refusal(["top"])
    if not tops or abs(tops[0].x - estimate) <= EPSILON:
        return [report]
    change = setter(facts.pins, "top", estimate, tops[0].y)
    return [report, change] if change is not None else [report]


# Rename & delete ---------------------------------------------------------
def renamer(find: str, replace: str, regex: bool) -> Callable[[str], str]:
    """The name substitution; a bad pattern raises ``ValueError("Pattern error: …")`` at once."""
    if not find:
        return lambda name: name
    if not regex:
        return lambda name: name.replace(find, replace)
    try:
        pattern = re.compile(find)
        pattern.sub(replace, "")
    except (re.error, IndexError) as error:
        raise ValueError(f"Pattern error: {error}") from error

    def substitute(name: str) -> str:
        try:
            return pattern.sub(replace, name)
        except (re.error, IndexError) as error:
            raise ValueError(f"Pattern error: {error}") from error

    return substitute


def rename_changes(facts: Facts, rename: Callable[[str], str]) -> list[Change]:
    """Rename Bulk: rename matching anchors; empty or clashing new names are refused."""
    pins = facts.pins
    plans = [(index, pin.name, rename(pin.name)) for index, pin in enumerate(pins)]
    moved = [(index, old, new) for index, old, new in plans if new != old]
    kept = Counter(new for _, old, new in plans)
    staying = {pin.name for index, pin in enumerate(pins) if all(index != i for i, _, _ in moved)}
    changes = []
    for index, old, new in moved:
        problem = ""
        if not new:
            problem = "the new name is empty"
        elif new in staying:
            problem = f"{new} is already used on this layer"
        elif kept[new] > 1:
            problem = f"several anchors would become {new}"
        changes.append(Change(old, old, new or "–", None if problem else ("rename", index, new), problem))
    return changes


def delete_changes(facts: Facts, names: Iterable[str]) -> list[Change]:
    """Delete By Name: remove every anchor whose name is ticked."""
    wanted = set(names)
    return [Change(pin.name, point_text(pin.x, pin.y), "deleted", ("remove", index))
            for index, pin in enumerate(facts.pins) if pin.name in wanted]  # fmt: skip


def census(rows: Iterable[tuple[Iterable[Pin], bool]]) -> dict[str, list[int]]:
    """Delete By Name list: ``{name: [editable layers, auto layers]}`` over ``(pins, auto)`` rows."""
    counts: dict[str, list[int]] = {}
    for pins, auto in rows:
        for name in dict.fromkeys(pin.name for pin in pins):
            counts.setdefault(name, [0, 0])[1 if auto else 0] += 1
    return dict(sorted(counts.items()))


# Clean-up ----------------------------------------------------------------
def opposite_changes(facts: Facts) -> list[Change]:
    """Remove Extraneous Mark Anchors: a mark with ``_top`` loses ``bottom``; with ``_bottom``, ``top``."""
    names = {pin.name for pin in facts.pins}
    doomed = {extra for mark, extra in OPPOSITES if mark in names}
    return [Change(pin.name, point_text(pin.x, pin.y), "removed", ("remove", index))
            for index, pin in enumerate(facts.pins) if pin.name in doomed]  # fmt: skip


def findings(pins: Sequence[Pin]) -> list[tuple[str, list[int]]]:
    """Duplicates Finder: ``(kind, indices)`` groups; the first pin of each group is kept.

    "duplicate name": the same name, or ``name.1``-style copies when ``name`` exists.
    "coincident": pins of different names at one rounded position.
    """
    if any(not isfinite(value) for pin in pins for value in (pin.x, pin.y)):
        raise ValueError("Anchor coordinates must be finite.")
    names = {pin.name for pin in pins}

    def family(name: str) -> str:
        stem, dot, tail = name.rpartition(".")
        return stem if dot and tail.isdigit() and stem in names else name

    groups: dict[str, list[int]] = {}
    for index, pin in enumerate(pins):
        groups.setdefault(family(pin.name), []).append(index)
    spots: dict[tuple[int, int], list[int]] = {}
    for index, pin in enumerate(pins):
        if len(groups[family(pin.name)]) == 1:
            spots.setdefault((round(pin.x), round(pin.y)), []).append(index)
    return [(kind, group) for kind, collection in (("duplicate name", groups), ("coincident", spots))
            for group in collection.values() if len(group) > 1]  # fmt: skip


def duplicate_changes(facts: Facts, coincident: bool) -> list[Change]:
    """Remove every extra duplicate; coincident extras only when ``coincident`` is ticked."""
    changes = []
    for kind, group in findings(facts.pins):
        keep = facts.pins[group[0]]
        for index in group[1:]:
            pin = facts.pins[index]
            text = f"{kind} of {keep.name}"
            edit = ("remove", index) if kind != "coincident" or coincident else None
            changes.append(Change(pin.name, point_text(pin.x, pin.y), text if edit else f"{text} (kept)", edit))
    return changes


# Writes and read-back ----------------------------------------------------
def expected(pins: Sequence[Pin], edits: Sequence[Edit]) -> list[Pin]:
    """The pins after ``edits``, in snapshot order with new anchors at the end."""
    result: list[Pin | None] = list(pins)
    for edit in edits:
        if edit[0] == "remove":
            result[edit[1]] = None
        elif edit[0] == "rename":
            result[edit[1]] = result[edit[1]]._replace(name=edit[2])  # type: ignore[union-attr]
    for edit in edits:
        if edit[0] == "set":
            name, (x, y) = edit[1], edit[2]
            spot = next((i for i, pin in enumerate(result) if pin is not None and pin.name == name), None)
            if spot is None:
                result.append(Pin(name, x, y))
            else:
                result[spot] = Pin(name, x, y)
    return [pin for pin in result if pin is not None]


def verify(where: str, before: Sequence[Pin], edits: Sequence[Edit], stored: Sequence[Pin]) -> list[str]:
    """Problems after a write: missing/extra names, moves beyond ``TOLERANCE`` and swallowed moves.

    For a "set" only a changed coordinate is checked (FontLab may round an
    untouched one). A move that FontLab rounded back to the old value is a
    problem: "x move 100 → 100.4 rounded to no change".
    """
    planned = expected(before, edits)
    problems = []
    want, have = Counter(pin.name for pin in planned), Counter(pin.name for pin in stored)
    for name in sorted(set(want) | set(have)):
        if want[name] != have[name]:
            problems.append(f"{where}: {name} stored {have[name]} times, planned {want[name]}")
    olds = {pin.name: pin for pin in before}
    found = {pin.name: pin for pin in stored}
    for edit in edits:
        if edit[0] != "set" or edit[1] not in found:
            continue
        name, new, old, got = edit[1], edit[2], olds.get(edit[1]), found[edit[1]]
        for axis, index in (("x", 0), ("y", 1)):
            start = None if old is None else old[index + 1]
            value = got[index + 1]
            if start is not None and abs(new[index] - start) <= EPSILON:
                continue
            if start is not None and abs(value - start) <= EPSILON:
                problems.append(f"{where}: {name} {axis} move {fmt(start)} → {fmt(new[index])} rounded to no change")
            elif abs(value - new[index]) > TOLERANCE:
                problems.append(f"{where}: {name} {axis} {fmt(value)}, planned {fmt(new[index])}")
    return problems


# Overlays (read-only) ----------------------------------------------------
def marker(x: float, y: float, size: float) -> OverlayContour:
    """A small diamond at (x, y) for the anchor cloud."""
    return OverlayContour(tuple(OverlayPoint(px, py) for px, py in ((x, y + size), (x + size, y), (x, y - size), (x - size, y))))


def ring(x: float, y: float, radius: float) -> OverlayContour:
    """An octagon of ``radius`` around (x, y) for stacked anchors."""
    from math import cos, pi, sin

    return OverlayContour(tuple(OverlayPoint(x + radius * cos(i * pi / 4), y + radius * sin(i * pi / 4)) for i in range(8)))


def outline(rings: Iterable[Ring]) -> tuple[OverlayContour, ...]:
    return tuple(OverlayContour(tuple(OverlayPoint(x, y) for x, y in points)) for points in rings if len(points) > 2)


def stacked(pins: Sequence[Pin]) -> list[list[Pin]]:
    """Groups of anchors that lie less than ``STACK_DISTANCE`` apart (three coincident → one group of 3)."""
    groups: list[list[Pin]] = []
    for pin in pins:
        home = next((g for g in groups if any(abs(p.x - pin.x) < STACK_DISTANCE and abs(p.y - pin.y) < STACK_DISTANCE
                                              for p in g)), None)  # fmt: skip
        if home is None:
            groups.append([pin])
        else:
            home.append(pin)
    return [group for group in groups if len(group) > 1]


def rings_overlay(pins: Sequence[Pin], size: int) -> Overlay:
    """One ring per stacked anchor, each a little larger, so three coincident anchors show three rings."""
    contours = []
    for group in stacked(pins):
        for depth, pin in enumerate(group):
            contours.append(ring(pin.x, pin.y, size * (1.5 + depth)))
    return Overlay(tuple(contours))


def extremes(points: Sequence[tuple[float, float]]) -> str:
    """"x a…b, y c…d" of the cloud, or "" when empty."""
    if not points:
        return ""
    xs, ys = [x for x, _ in points], [y for _, y in points]
    return f"x {fmt(min(xs))}…{fmt(max(xs))}, y {fmt(min(ys))}…{fmt(max(ys))}"


__all__ = [
    "APPEARANCE", "BOUNDS_ANCHORS", "METRICS", "REFERENCES", "TOLERANCE",
    "Change", "Facts", "Overlay", "Pin", "bounds_changes", "census", "centre_changes",
    "delete_changes", "duplicate_changes", "estimate_rings", "expected", "findings",
    "metric_value", "opposite_changes", "optical_changes", "rename_changes", "renamer",
    "rings_overlay", "round_changes", "snap", "snap_changes", "stacked", "subject", "verify",
]  # fmt: skip
