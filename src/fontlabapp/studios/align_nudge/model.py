# this_file: src/fontlabapp/studios/align_nudge/model.py
# SPDX-License-Identifier: Apache-2.0
"""Pure planners of Align & Nudge: align/distribute, interpolated nudge, overlap nodes, simplify.

What: each planner reads a ``transform_studio.geometry.Layer`` snapshot and
returns ``Change`` rows whose ``edit`` holds snapshot steps (``("node", …)``,
``("shape", …)``, ``("remove", …)``), or a skip note string. Nothing here
touches FontLab, so every rule is tested without the host.
Why: behaviour parity with the Scriptmix ``Scripts/Contours`` tools Align And
Distribute, Interpolated Nudge, Overlap Nodes and Simplify Selected Nodes, whose
behaviour is restated in each function's docstring.
"""

import math
from collections.abc import Sequence

from fontlabapp.studios.transform_studio.geometry import (
    IDENTITY,
    Change,
    Contour,
    Layer,
    apply,
    concat,
    corners,
    finite,
    invert,
    is_identity,
    is_translation,
    translate,
)

OPERATIONS = (
    ("Left", "left"),
    ("Right", "right"),
    ("Horizontal center", "horizontal"),
    ("Bottom", "bottom"),
    ("Top", "top"),
    ("Vertical center", "vertical"),
    ("Distribute horizontally", "distribute_x"),
    ("Distribute vertically", "distribute_y"),
)
GEOMETRY = ("Selected geometry", "All nodes")
REFERENCES = ("Selection bounds", "Coordinate")
COORDINATE_RANGE = (-1000000.0, 1000000.0)
NUDGE_RANGE = (-1000.0, 1000.0)
NUDGE_DEFAULT = (0.0, 10.0)
DISTRIBUTE_ALL = "Distribution needs selected nodes; choose Selected geometry."
FINITE_RANGE = "Geometry exceeds the finite coordinate range."
NUDGE_FINITE = "Nudge distances must be finite."
NUDGE_SELECT = "Select one or more on-curve nodes."
NUDGE_EMPTY = "select on-curve nodes and set a nonzero nudge"
ITALIC_ERROR = "The italic angle must be finite and between -89° and 89°."
CONFLICT = "Selected tips give conflicting targets; select one tip per corner."
TWO_OWNERS = "a curve handle has two selected owners"
STRUCTURE = "Master node structures differ."
COUNTS = "Master contour counts differ."
XY = tuple[float, float]


def _kept(item: str, reason: str) -> Change:
    return Change(item, "", f"{reason}, kept")


def _notes(notes: Sequence[str]) -> list[Change]:
    """One row per distinct note with its shape count (``writer.note_rows``)."""
    counts: dict[str, int] = {}
    for text in notes:
        counts[text] = counts.get(text, 0) + 1
    return [
        Change(f"{n} shape" + ("" if n == 1 else "s"), "", text)
        for text, n in counts.items()
    ]


def outline_shapes(layer: Layer) -> tuple[list[int], list[str]]:
    """Indices of own contour shapes editable in place, and notes for shared or scaled/rotated ones."""
    editable, notes = [], []
    for s, shape in enumerate(layer.shapes):
        if shape.component or not shape.contours:
            continue
        if shape.shared:
            notes.append("shared outline, kept")
        elif not is_translation(shape.matrix):
            notes.append("scaled or rotated shape, kept")
        else:
            editable.append(s)
    return editable, notes


# Align and distribute -----------------------------------------------------
# A group: kind, shape index, member entries (s, c, i, glyph xy) and glyph-space bounding points.
Group = tuple[str, int, list[tuple[int, int, int, XY]], list[XY]]


def contour_groups(
    layer: Layer, s: int, c: int, all_nodes: bool, distribute: bool
) -> list[Group]:
    """Pair each selected on-curve node with its unselected adjacent controls (whole contours move as units)."""
    shape, contour = layer.shapes[s], layer.shapes[s].contours[c]
    nodes = contour.nodes
    chosen = [i for i, node in enumerate(nodes) if all_nodes or node.selected]
    if not chosen:
        return []
    if not is_identity(contour.matrix):
        raise ValueError("contour has its own transform")
    entries = [(s, c, i, apply(shape.matrix, n.x, n.y)) for i, n in enumerate(nodes)]
    if not distribute and len(chosen) == len(nodes):
        return [("contour", s, entries, [e[3] for e in entries])]
    groups, claimed = [], {}
    for index in chosen:
        members = [entries[index]]
        if nodes[index].on:
            for neighbour in (index - 1, index + 1):
                if not contour.closed and not 0 <= neighbour < len(nodes):
                    continue
                neighbour %= len(nodes)
                if nodes[neighbour].on or neighbour in chosen:
                    continue
                if claimed.get(neighbour, index) != index:
                    raise ValueError(TWO_OWNERS)
                if neighbour not in claimed:
                    members.append(entries[neighbour])
                claimed[neighbour] = index
        groups.append(("node", s, members, [entries[index][3]]))
    return groups


def node_groups(
    layer: Layer, all_nodes: bool, distribute: bool
) -> tuple[list[Group], list[Change]]:
    groups, notes = [], []
    for s, shape in enumerate(layer.shapes):
        if shape.component:
            continue
        contours = [
            c
            for c, contour in enumerate(shape.contours)
            if any(all_nodes or n.selected for n in contour.nodes)
        ]
        if not contours:
            continue
        label = f"shape {s + 1}"
        if shape.locked:
            notes.append(_kept(label, "locked shape"))
            continue
        if shape.shared:
            notes.append(_kept(label, "shared outline data"))
            continue
        for number, c in enumerate(contours, 1):
            try:
                groups.extend(contour_groups(layer, s, c, all_nodes, distribute))
            except ValueError as error:
                notes.append(_kept(f"{label}, contour {number}", str(error)))
    return groups, notes


def component_groups(layer: Layer) -> tuple[list[Group], list[Change]]:
    """Selected component rectangles; their base outlines are never edited."""
    groups, notes = [], []
    for s, shape in enumerate(layer.shapes):
        if not shape.component or not shape.selected:
            continue
        if shape.locked:
            notes.append(_kept(f"component {s + 1}", "locked component"))
            continue
        points = corners(shape)
        if not points:
            notes.append(_kept(f"component {s + 1}", "no bounding box"))
            continue
        groups.append(("component", s, [], points))
    return groups, notes


def position(points: Sequence[XY], axis: int, fraction: float) -> float:
    values = [p[axis] for p in points]
    low, high = min(values), max(values)
    value = low * (1 - fraction) + high * fraction
    if not math.isfinite(value):
        raise ValueError(FINITE_RANGE)
    return value


def group_steps(layer: Layer, group: Group, dx: float, dy: float) -> tuple:
    if not finite(dx, dy):
        raise ValueError(FINITE_RANGE)
    kind, s, entries, _ = group
    if kind == "component":
        return (("shape", s, concat(layer.shapes[s].matrix, translate(dx, dy)), False),)
    back = invert(layer.shapes[s].matrix)
    return tuple(
        ("node", s, c, i, *apply(back, x + dx, y + dy), None)
        for s, c, i, (x, y) in entries
    )


def align_changes(
    layer: Layer, mode: str, all_nodes: bool = False, coordinate: float | None = None
) -> list[Change]:
    """Align And Distribute ``plan_layer``: align to the bounds or a coordinate, or distribute nodes.

    Whole selected contours move as units, partial contours contribute
    selected nodes with their unselected handles, components move by their
    transform. Distribution sorts by the axis (ties keep contour/node order),
    keeps both endpoints and needs three or more items. Anchors never move.
    """
    if mode not in {key for _, key in OPERATIONS}:
        raise ValueError("Choose a supported operation.")
    if coordinate is not None and not math.isfinite(coordinate):
        raise ValueError("Enter a finite coordinate.")
    distribute = mode.startswith("distribute_")
    if distribute and all_nodes:
        raise ValueError(DISTRIBUTE_ALL)
    has_nodes = any(
        all_nodes or n.selected
        for sh in layer.shapes
        if not sh.component
        for c in sh.contours
        for n in c.nodes
    )
    has_components = (
        not distribute
        and not all_nodes
        and any(sh.component and sh.selected for sh in layer.shapes)
    )
    if not has_nodes and not has_components:
        return []
    if layer.locked or not layer.body:
        return [_kept("layer", "locked or non-body layer")]
    groups, notes = node_groups(layer, all_nodes, distribute)
    if not distribute and not all_nodes:
        components, more = component_groups(layer)
        groups, notes = groups + components, notes + more
    if not groups:
        return notes
    if distribute and len(groups) < 3:
        return notes + [_kept("nodes", "select at least three nodes to distribute")]
    axis = 0 if mode in {"left", "right", "horizontal", "distribute_x"} else 1
    fraction = (
        0.5
        if mode in {"horizontal", "vertical"}
        else 0.0
        if mode in {"left", "bottom"} or distribute
        else 1.0
    )
    points = [p for group in groups for p in group[3]]
    try:
        target = position(points, axis, fraction) if coordinate is None else coordinate
    except ValueError as error:
        return notes + [_kept("geometry", str(error))]
    if distribute:
        groups.sort(key=lambda group: group[3][0][axis])
    rows = list(notes)
    for index, group in enumerate(groups):
        try:
            old = position(group[3], axis, fraction)
            if distribute:
                target = position(points, axis, index / (len(groups) - 1))
            distance = target - old
            if abs(distance) <= 1e-8:
                continue
            steps = group_steps(
                layer,
                group,
                distance if axis == 0 else 0.0,
                distance if axis == 1 else 0.0,
            )
        except ValueError as error:
            rows.append(_kept(f"{group[0]} {index + 1}", str(error)))
            continue
        rows.append(
            Change(
                f"{group[0]} {index + 1}",
                f"{'xy'[axis]} {old:g}",
                f"{target:g} ({distance:+g})",
                steps,
            )
        )
    return rows


# Interpolated nudge -------------------------------------------------------
def nudged(
    points: Sequence[tuple[float, float, bool]],
    selected: set[int],
    dx: float,
    dy: float,
) -> list[XY]:
    """Scale cubic handles between simultaneously moved endpoints; factors clamp to 0…4 per axis."""
    if not finite(dx, dy):
        raise ValueError(NUDGE_FINITE)
    on = [i for i, p in enumerate(points) if p[2]]
    if not selected or not selected.issubset(set(on)):
        raise ValueError(NUDGE_SELECT)
    shifts = {i: (dx, dy) if i in selected else (0.0, 0.0) for i in on}
    result = [(p[0], p[1]) for p in points]
    for index, start in enumerate(on):
        end = on[(index + 1) % len(on)]
        distance = (end - start) % len(points) or len(points)
        inside = [(start + j) % len(points) for j in range(1, distance)]
        if len(inside) not in (0, 2):
            raise ValueError("Use line or cubic segments.")
        for control, anchor in zip(inside, (start, end)):
            values = []
            for axis in (0, 1):
                span = points[end][axis] - points[start][axis]
                delta = shifts[end][axis] - shifts[start][axis]
                factor = (
                    max(0.0, min(4.0, (span + delta) / span))
                    if abs(span) > 1e-9
                    else 1.0
                )
                values.append(
                    points[anchor][axis]
                    + shifts[anchor][axis]
                    + (points[control][axis] - points[anchor][axis]) * factor
                )
            result[control] = (values[0], values[1])
    for index in on:
        result[index] = (
            points[index][0] + shifts[index][0],
            points[index][1] + shifts[index][1],
        )
    return result


def nudge_changes(layer: Layer, dx: float, dy: float) -> list[Change]:
    """Interpolated Nudge: one row per closed cubic contour with selected on-curve nodes."""
    if not finite(dx, dy):
        raise ValueError(NUDGE_FINITE)
    shapes, notes = outline_shapes(layer)
    rows = []
    for s in shapes:
        for c, contour in enumerate(layer.shapes[s].contours):
            if contour.tt or not contour.closed:
                notes.append("open or quadratic contour, kept")
                continue
            selected = {i for i, n in enumerate(contour.nodes) if n.selected and n.on}
            if not selected:
                continue
            result = nudged([(n.x, n.y, n.on) for n in contour.nodes], selected, dx, dy)
            steps = tuple(("node", s, c, i, x, y, None) for i, (n, (x, y)) in enumerate(zip(contour.nodes, result))
                          if abs(n.x - x) > 1e-6 or abs(n.y - y) > 1e-6)  # fmt: skip
            if steps:
                rows.append(
                    Change(
                        "selected nodes", str(len(selected)), f"{dx:g}, {dy:g}", steps
                    )
                )
    if not rows:
        notes.append(NUDGE_EMPTY)
    return rows + _notes(notes)


# Overlap nodes ------------------------------------------------------------
def _overlap_contour(
    layer: Layer, s: int, c: int, shear: float
) -> dict[int, tuple[float, float, bool | None]]:
    contour, (ox, _) = layer.shapes[s].contours[c], layer.shapes[s].matrix[4:6]
    nodes, planned = contour.nodes, {}
    for index, node in enumerate(nodes):
        if not node.selected or not node.on:
            continue
        for direction in (1, -1):
            indices = [index + direction * step for step in (1, 2)]
            if len(nodes) < 3 or (
                not contour.closed and any(i < 0 or i >= len(nodes) for i in indices)
            ):
                continue
            ci, hi = (i % len(nodes) for i in indices)
            corner, handle = nodes[ci], nodes[hi]
            if not corner.on or handle.on:
                continue
            x = math.trunc(node.x + ox + shear * (handle.y - node.y)) - ox
            for key, item in ((ci, (node.x, node.y, False)), (hi, (x, handle.y, None))):
                if key in planned and planned[key] != item:
                    raise ValueError(CONFLICT)
                planned[key] = item
            break
    return planned


def overlap_changes(layer: Layer, angle: float) -> list[Change]:
    """Overlap Nodes: move each selected tip's adjacent corner onto it and align the next handle.

    The next corner is tried first, then the previous one. The corner becomes
    sharp; the handle x follows the master's italic angle (FontLab sign,
    negated), truncated to an integer in glyph space; handle y stays.
    """
    if not math.isfinite(angle) or not -89 < angle < 89:
        raise ValueError(ITALIC_ERROR)
    shear = -math.tan(math.radians(angle))
    rows = []
    for s, shape in enumerate(layer.shapes):
        if shape.component:
            continue
        for c, contour in enumerate(shape.contours):
            if not any(n.selected for n in contour.nodes):
                continue
            problem = _overlap_problem(layer, shape.locked, shape.shared, contour)
            if problem:
                raise ValueError(problem)
            if not is_translation(shape.matrix):
                raise ValueError(
                    "Overlap Nodes needs an unscaled, unrotated selected outline."
                )
            if contour.tt:
                rows.append(Change("contour", "", "quadratic contour kept"))
                continue
            steps = []
            for i, (x, y, smooth) in _overlap_contour(layer, s, c, shear).items():
                node = contour.nodes[i]
                if (
                    abs(node.x - x) > 1e-8
                    or abs(node.y - y) > 1e-8
                    or (smooth is not None and node.smooth != smooth)
                ):
                    steps.append(("node", s, c, i, x, y, smooth))
            if steps:
                rows.append(
                    Change(
                        "tip neighbours",
                        str(len(steps)),
                        f"overlap · italic {angle:g}°",
                        tuple(steps),
                    )
                )
    return rows


def _overlap_problem(layer: Layer, locked: bool, shared: bool, contour: Contour) -> str:
    if not finite(*(v for n in contour.nodes for v in (n.x, n.y))):
        return "Selected contour has non-finite coordinates."
    if layer.locked or locked:
        return "Unlock the selected layer and shape first."
    if shared:
        return "Selected outline data is shared; unlink it first."
    if contour.matrix != IDENTITY:
        return "Bake the selected contour transform first."
    return ""


# Simplify selected nodes --------------------------------------------------
def removals(contour: Contour, selected: Sequence[int] | None = None) -> list[int]:
    """Alternate selected indices of a polygon; open endpoints stay; closed keep ≥ 3 nodes, open ≥ 2."""
    nodes = contour.nodes
    if any(not n.on for n in nodes):
        return []
    chosen = (
        [i for i, n in enumerate(nodes) if n.selected]
        if selected is None
        else list(selected)
    )
    candidates = chosen[1::2]
    if not contour.closed:
        candidates = [i for i in candidates if 0 < i < len(nodes) - 1]
    minimum = 3 if contour.closed else 2
    return candidates[: max(0, len(nodes) - minimum)]


def simplify_changes(layer: Layer, reference: Layer | None = None) -> list[Change]:
    """Simplify Selected Nodes: remove alternate selected nodes, using the reference (preview master) selection."""
    shapes, notes = outline_shapes(layer)
    ref_shapes = outline_shapes(reference)[0] if reference is not None else shapes
    base = reference if reference is not None else layer
    originals = [contour for s in ref_shapes for contour in base.shapes[s].contours]
    current = [
        (s, c, contour)
        for s in shapes
        for c, contour in enumerate(layer.shapes[s].contours)
    ]
    if len(originals) != len(current):
        return [Change("contours", "", "", problem=COUNTS)]
    rows = []
    for number, ((s, c, contour), original) in enumerate(zip(current, originals), 1):
        if (len(original.nodes) != len(contour.nodes) or original.closed != contour.closed
                or [n.on for n in original.nodes] != [n.on for n in contour.nodes]):  # fmt: skip
            return [Change("nodes", "", "", problem=STRUCTURE)]
        indices = removals(
            contour, [i for i, n in enumerate(original.nodes) if n.selected]
        )
        if indices:
            count = len(contour.nodes)
            rows.append(Change(f"contour {number}", str(count), str(count - len(indices)),
                               (("remove", s, c, tuple(indices), count - len(indices)),), key=(number, tuple(indices))))  # fmt: skip
    return rows + _notes(notes)
