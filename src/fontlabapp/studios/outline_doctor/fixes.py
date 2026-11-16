# this_file: src/fontlabapp/studios/outline_doctor/fixes.py
# SPDX-License-Identifier: Apache-2.0
"""Outline Doctor fixes: planners, native writers and read-back checks.

What: the eleven Scriptmix outline fixers, ported with their thresholds,
options, row texts and checks: Delete Small/Duplicate Contours, Add Extremes,
Fix Zero Handles, Delete Close Points, Straighten Short Curves, Curve All
Straights, Straighten All Curves, Retract Handles, Round Coordinates and
Remove Overlap. Every planner reads only; ``write_*`` runs inside the
session's single history step; ``verify_*`` returns mismatch texts.
Why: ``checks.CHECKS`` registers each trio so one session drives them all.
Each planner also returns the after-geometry the TGlyph ghost draws.
"""

import math
from collections.abc import Mapping
from typing import Any

import fontlabapp.core.outline as outline

from .._contours import node_spans, spans
from .model import (
    EPSILON,
    Context,
    Issue,
    after,
    contours,
    fmt,
    node_points,
    note_rows,
    outline_shapes,
    plural,
    segments_of,
    translation,
    unsigned_area,
)

MARGIN = 0.02
ZERO = 0.5
CLOSE = 0.1002
OPEN_NOTE = "open contour, kept"
OPEN_TT_NOTE = "open or quadratic contour, kept"
SMOOTH_NOTE = "final control has Smooth set (fl#8517), kept"
UNSUPPORTED_NOTE = "unsupported segment structure, kept"


# Shared writers ----------------------------------------------------------------
def write_removals(layer: Any, edits: list, options: Mapping[str, Any]) -> None:
    for shape, contour, _ in edits:
        shape.removeContour(contour)
        shape.changed()


def removal_edits(issues: list[Issue]) -> list[Issue]:
    """Attach the expected contour count of each shape to its removals."""
    counts: dict[int, int] = {}
    for issue in issues:
        if issue.edit is not None:
            shape = issue.edit[0]
            counts[id(shape)] = counts.get(id(shape), len(list(shape.contours))) - 1
    return [issue._replace(edit=(issue.edit[0], issue.edit[1], counts[id(issue.edit[0])]))
            if issue.edit is not None else issue for issue in issues]  # fmt: skip


def verify_removals(layer: Any, edits: list) -> list[str]:
    found = {f"{layer.name}: {len(list(s.contours))} of {n} contours"
             for s, _, n in edits if len(list(s.contours)) != n}  # fmt: skip
    return sorted(found)


def write_moves(layer: Any, edits: list, options: Mapping[str, Any]) -> None:
    for moves in edits:
        for node, x, y in moves:
            node.x, node.y = x, y


def verify_moves(layer: Any, edits: list) -> list[str]:
    wrong = [1 for moves in edits for node, x, y in moves if abs(node.x - x) > 0.01 or abs(node.y - y) > 0.01]
    return [f"{layer.name}: {plural(len(wrong), 'node')} off the plan"] if wrong else []


def replaced(points: list, changes: Mapping[int, tuple[float, float]]) -> list:
    return [(*changes[i], on) if i in changes else (x, y, on) for i, (x, y, on) in enumerate(points)]


def dropped(points: list, indices: set[int]) -> list:
    return [p for i, p in enumerate(points) if i not in indices]


# Delete Small Contours ---------------------------------------------------------
def plan_small(layer: Any, options: Mapping[str, Any], context: Context) -> list[Issue]:
    threshold = float(options["threshold"])
    rows, notes = [], outline_shapes(layer)[1]
    for number, position, index, shape, contour in contours(layer):
        if not contour.closed:
            notes.append(OPEN_NOTE)
            continue
        points = node_points(contour)
        area = unsigned_area(segments_of(points, bool(contour.isTT)))
        if area >= threshold:
            continue
        dx, dy = translation(shape) or (0.0, 0.0)
        x, y = min(p[0] for p in points) + dx, min(p[1] for p in points) + dy
        rows.append(Issue(f"contour {number}", f"area {area:.0f}", f"delete at {fmt(x)}, {fmt(y)}",
                          (shape, contour), key=number, after=after(position, index, None, shape)))  # fmt: skip
    return removal_edits(rows) + note_rows(notes)


# Delete Duplicate Contours -----------------------------------------------------
def same_cycle(a: list, b: list, tolerance: float) -> bool:
    if len(a) != len(b) or not a:
        return False

    def close(p: tuple, q: tuple) -> bool:
        return p[2] == q[2] and abs(p[0] - q[0]) <= tolerance and abs(p[1] - q[1]) <= tolerance

    return any(all(close(p, q) for p, q in zip(a, b[s:] + b[:s], strict=True)) for s in range(len(b)))


def plan_duplicates(layer: Any, options: Mapping[str, Any], context: Context) -> list[Issue]:
    tolerance = float(options["tolerance"])
    notes, items = outline_shapes(layer)[1], []
    for _, position, index, shape, contour in contours(layer):
        if not contour.closed:
            notes.append(OPEN_NOTE)
            continue
        dx, dy = translation(shape) or (0.0, 0.0)
        items.append((position, index, shape, contour, [(x + dx, y + dy, on) for x, y, on in node_points(contour)]))
    protected = {i for i, item in enumerate(items)
                 if any(i != j and same_cycle(item[4], other[4][::-1], tolerance) for j, other in enumerate(items))}  # fmt: skip
    rows, seen = [], []
    for i, (position, index, shape, contour, points) in enumerate(items):
        number = i + 1
        if i in protected:
            rows.append(Issue(f"contour {number}", "", "reversed duplicate, kept"))
            continue
        first = next((n for n, other in seen if same_cycle(other, points, tolerance)), None)
        if first is None:
            seen.append((number, points))
        else:
            rows.append(Issue(f"contour {number}", f"same as contour {first}", "delete", (shape, contour),
                              key=number, after=after(position, index, None, shape)))  # fmt: skip
    return removal_edits(rows) + note_rows(notes)


# Add Extremes --------------------------------------------------------------------
def cubic_runs(points: list) -> list[tuple[int, int, tuple]]:
    """(segment number, start index, cubic) from ``points[0]`` (the original ``segments``)."""
    result, start, handles, k, at = [], points[0][:2], [], 0, 0
    for i, (x, y, on) in enumerate(points[1:] + points[:1], 1):
        if not on:
            handles.append((x, y))
            continue
        if len(handles) == 2:
            result.append((k, at, (start, handles[0], handles[1], (x, y))))
        k, at, start, handles = k + 1, i % len(points), (x, y), []
    return result


def roots(a: float, b: float, c: float) -> list[float]:
    if abs(a) < 1e-9:
        found = [-c / b] if abs(b) > 1e-9 else []
    else:
        disc = b * b - 4 * a * c
        if disc < 0:
            return []
        q = math.sqrt(disc)
        found = [(-b + q) / (2 * a), (-b - q) / (2 * a)]
    return sorted({round(t, 6) for t in found if MARGIN < t < 1 - MARGIN})


def extremes(p0: tuple, p1: tuple, p2: tuple, p3: tuple) -> list[float]:
    found: set[float] = set()
    for axis in (0, 1):
        a = -p0[axis] + 3 * p1[axis] - 3 * p2[axis] + p3[axis]
        b = 2 * (p0[axis] - 2 * p1[axis] + p2[axis])
        found.update(roots(a, b, p1[axis] - p0[axis]))
    return sorted(found)


def bezier(cubic: tuple, t: float) -> tuple[float, float]:
    u = 1 - t
    return tuple(u**3 * cubic[0][i] + 3 * u * u * t * cubic[1][i] + 3 * u * t * t * cubic[2][i] + t**3 * cubic[3][i]
                 for i in (0, 1))  # fmt: skip


def extreme_plan(points: list) -> list[tuple[int, int, list[float]]]:
    if not points or not points[0][2]:
        return []
    result = []
    for k, at, cubic in cubic_runs(points):
        cuts, accepted = [], [cubic[0], cubic[3]]
        for t in reversed(extremes(*cubic)):
            point = bezier(cubic, t)
            if any(abs(point[0] - p[0]) + abs(point[1] - p[1]) < CLOSE for p in accepted):
                continue
            cuts.append(t)
            accepted.append(point)
        if cuts:
            result.append((k, at, sorted(cuts)))
    return result


def split(cubic: tuple, ts: list[float]) -> list[tuple[float, float, bool]]:
    """Inner nodes after cutting ``cubic`` at every ``t`` (de Casteljau)."""
    nodes, rest, done = [], cubic, 0.0
    for t in sorted(ts):
        local = (t - done) / (1 - done)
        p0, p1, p2, p3 = rest
        a = [p0[i] + (p1[i] - p0[i]) * local for i in (0, 1)]
        b = [p1[i] + (p2[i] - p1[i]) * local for i in (0, 1)]
        c = [p2[i] + (p3[i] - p2[i]) * local for i in (0, 1)]
        d = [a[i] + (b[i] - a[i]) * local for i in (0, 1)]
        e = [b[i] + (c[i] - b[i]) * local for i in (0, 1)]
        m = [d[i] + (e[i] - d[i]) * local for i in (0, 1)]
        nodes += [(*a, False), (*d, False), (*m, True)]
        rest, done = (tuple(m), tuple(e), tuple(c), p3), t
    return nodes + [(*rest[1], False), (*rest[2], False)]


def with_extremes(points: list, plan: list) -> list:
    result = list(points)
    for _, at, ts in sorted(plan, key=lambda item: item[1], reverse=True):
        cubic = (result[at][:2], result[at + 1][:2], result[at + 2][:2], result[(at + 3) % len(result)][:2])
        result[at + 1 : at + 3] = split(cubic, ts)
    return result


def plan_extremes(layer: Any, options: Mapping[str, Any], context: Context) -> list[Issue]:
    rows = []
    for number, position, index, shape, contour in contours(layer):
        if not contour.closed or contour.isTT:
            continue
        points = node_points(contour)
        plan = extreme_plan(points)
        count = sum(len(ts) for _, _, ts in plan)
        if not count:
            continue
        nodes = int(contour.nodesCount)
        rows.append(Issue(f"contour {number}", plural(nodes, "node"), f"+{plural(count, 'extreme')}",
                          (contour, [(k, ts) for k, _, ts in plan], nodes + 3 * count),
                          key=(number, tuple((k, len(ts)) for k, _, ts in plan)),
                          after=after(position, index, with_extremes(points, plan), shape)))  # fmt: skip
    return rows + note_rows(outline_shapes(layer)[1])


def write_extremes(layer: Any, edits: list, options: Mapping[str, Any]) -> None:
    for contour, plan, _ in edits:
        for k, ts in sorted(plan, reverse=True):
            upper = 1.0
            for t in sorted(ts, reverse=True):
                contour.insertNodeTo(k + t / upper)
                upper = t


def verify_counts(layer: Any, edits: list) -> list[str]:
    return [f"{layer.name}: {int(e[0].nodesCount)} of {e[-1]} nodes" for e in edits if int(e[0].nodesCount) != e[-1]]


# Fix Zero Handles --------------------------------------------------------------
def cubic_indices(points: list) -> list[tuple[int, int, int, int]]:
    on = [i for i, p in enumerate(points) if p[2]]
    result = []
    for k, start in enumerate(on):
        end = on[(k + 1) % len(on)]
        span = (end - start) % len(points) or len(points)
        between = [(start + j) % len(points) for j in range(1, span)]
        if len(between) == 2:
            result.append((start, between[0], between[1], end))
    return result


def third(base: float, other: float) -> float:
    return float(math.floor(base + (other - base) / 3 + 0.5))


def plan_zero(layer: Any, options: Mapping[str, Any], context: Context) -> list[Issue]:
    pull, rows = bool(options["pull"]), []
    for number, position, index, shape, contour in contours(layer):
        if contour.isTT:
            continue
        points = node_points(contour)
        lines, singles = [], []
        for i0, i1, i2, i3 in cubic_indices(points):
            first = math.dist(points[i0][:2], points[i1][:2]) < ZERO
            second = math.dist(points[i3][:2], points[i2][:2]) < ZERO
            if first and second:
                lines.append((i0, i1, i2, i3))
            elif first:
                singles.append((i1, i0, i2))
            elif second:
                singles.append((i2, i3, i1))
        if not lines and not singles:
            continue
        nodes, moves, changed = list(contour.nodes()), [], {}
        for handle, base, other in singles if pull else ():
            x = third(points[base][0], points[other][0])
            y = third(points[base][1], points[other][1])
            if math.hypot(x - points[handle][0], y - points[handle][1]) >= ZERO:
                moves.append((nodes[handle], x, y))
                changed[handle] = (x, y)
        found = f"{plural(len(lines), 'line')}, {plural(len(singles), 'single')}"
        if not lines and not moves:
            rows.append(Issue(f"contour {number}", found, "single handles kept"))
            continue
        done = [f"{len(lines)} to lines" if lines else "", f"{len(moves)} pulled" if moves else ""]
        ghost = dropped(replaced(points, changed), {i for line in lines for i in line[1:3]})
        rows.append(Issue(f"contour {number}", found, ", ".join(d for d in done if d),
                          (contour, [nodes[line[3]] for line in lines], moves, len(points) - 2 * len(lines)),
                          key=(number, tuple(line[0] for line in lines)) if lines else None,
                          after=after(position, index, ghost, shape)))  # fmt: skip
    return rows + note_rows(outline_shapes(layer)[1])


def write_zero(layer: Any, edits: list, options: Mapping[str, Any]) -> None:
    for _, ends, moves, _ in edits:
        for node, x, y in moves:
            node.x, node.y = x, y
        for node in ends:
            if node.convertToLine() is False:
                raise RuntimeError(f"FontLab did not straighten a curve in {layer.name}.")


def verify_zero(layer: Any, edits: list) -> list[str]:
    found = verify_counts(layer, edits)
    if any(abs(n.x - x) > 0.01 or abs(n.y - y) > 0.01 for e in edits for n, x, y in e[2]):
        found.append(f"{layer.name}: a handle did not move")
    return found


# Delete Close Points -----------------------------------------------------------
def arc_length(span: list[tuple[float, float]]) -> float:
    if len(span) == 2:
        return math.dist(span[0], span[1])
    samples = [bezier(tuple(span), i / 32) for i in range(33)]
    return sum(math.dist(a, b) for a, b in zip(samples, samples[1:], strict=False))


def plan_close(layer: Any, options: Mapping[str, Any], context: Context) -> list[Issue]:
    limit = float(options["distance"])
    if not math.isfinite(limit) or limit <= 0:
        raise ValueError("Distance must be finite and positive.")
    rows, notes = [], outline_shapes(layer)[1]
    for si, (position, shape) in enumerate(outline_shapes(layer)[0]):
        for ci, contour in enumerate(shape.contours):
            if contour.isTT or not contour.closed:
                notes.append(OPEN_TT_NOTE)
                continue
            points = node_points(contour)
            try:
                indexed = node_spans(list(range(len(points))), lambda i: points[i][2])
            except ValueError:
                notes.append(UNSUPPORTED_NOTE)
                continue
            lengths = [arc_length([points[i][:2] for i in edge]) for edge in indexed]
            picked = [n for n, length in enumerate(lengths) if length <= limit][: max(0, len(indexed) - 3)]
            if not picked:
                continue
            doomed = {i for n in picked for i in indexed[n][1:]}
            remaining = [p for i, p in enumerate(points) if i not in doomed]
            first = next(i for i, p in enumerate(remaining) if p[2])
            kept = remaining[first:] + remaining[:first]
            nodes = list(contour.nodes())
            survivors = [n for i, n in enumerate(nodes) if i not in doomed]
            if not kept[-1][2] and survivors[(first - 1) % len(survivors)].smooth:
                notes.append(SMOOTH_NOTE)
                continue
            rows.append(Issue(f"contour {ci + 1}", str(len(picked)), "merge", (contour, sorted(doomed), kept),
                              key=(si, ci, tuple(picked)), after=after(position, ci, kept, shape)))  # fmt: skip
    return rows + note_rows(notes)


def write_close(layer: Any, edits: list, options: Mapping[str, Any]) -> None:
    for contour, indices, _ in edits:
        for index in reversed(indices):
            contour.removeAt(index)
        nodes = list(contour.nodes())
        if nodes and not nodes[0].isOn():
            first = next(i for i, n in enumerate(nodes) if n.isOn())
            if contour.setStartPoint(first) is False:
                raise RuntimeError("FontLab refused the surviving start node.")


def verify_close(layer: Any, edits: list) -> list[str]:
    for contour, _, kept in edits:
        nodes = list(contour.nodes())
        if node_points(contour) != list(kept) or (nodes and not nodes[-1].isOn() and nodes[-1].smooth):
            return [str(layer.name)]
    return []


# Straighten Short Curves -------------------------------------------------------
def chord_offset(point: tuple, a: tuple, b: tuple) -> tuple[float, float]:
    (px, py), (ax, ay), (bx, by) = point, a, b
    dx, dy = bx - ax, by - ay
    length = math.hypot(dx, dy)
    if length == 0:
        return math.hypot(px - ax, py - ay), 0.0
    return abs((px - ax) * dy - (py - ay) * dx) / length, ((px - ax) * dx + (py - ay) * dy) / (length * length)


def plan_short(layer: Any, options: Mapping[str, Any], context: Context) -> list[Issue]:
    max_length, tolerance, rows = float(options["chord"]), float(options["handles"]), []
    for number, position, index, shape, contour in contours(layer):
        if contour.isTT:
            continue
        points = node_points(contour)
        curves, found = cubic_indices(points), []
        for i0, i1, i2, i3 in curves:
            a, b = points[i0][:2], points[i3][:2]
            length = math.dist(a, b)
            if length == 0 or length > max_length:
                continue
            d1, t1 = chord_offset(points[i1][:2], a, b)
            d2, t2 = chord_offset(points[i2][:2], a, b)
            if max(d1, d2) <= tolerance and 0 <= t1 <= 1 and 0 <= t2 <= 1:
                found.append((i0, i1, i2, i3, max(d1, d2)))
        if not found:
            continue
        nodes = list(contour.nodes())
        worst = max(f[4] for f in found)
        ghost = dropped(points, {i for f in found for i in f[1:3]})
        rows.append(Issue(f"contour {number}", plural(len(curves), "curve"), f"{len(found)} to lines (max {worst:.1f})",
                          (contour, [nodes[f[3]] for f in found], len(points) - 2 * len(found)),
                          key=(number, tuple(f[0] for f in found)), after=after(position, index, ghost, shape)))  # fmt: skip
    return rows + note_rows(outline_shapes(layer)[1])


def write_lines(layer: Any, edits: list, options: Mapping[str, Any]) -> None:
    for _, ends, _ in edits:
        for node in ends:
            if node.convertToLine() is False:
                raise RuntimeError("FontLab refused segment conversion.")


# Curve All Straights / Straighten All Curves -----------------------------------
def convert_plan(layer: Any, reference: Any, mode: str) -> list[Issue]:
    """The shared planner of Curve All Straights ("curve") and Straighten All Curves ("line")."""
    if reference is None:
        return [Issue("glyph", "", "no current selected layer, kept")]
    own, notes = outline_shapes(layer)
    ref_shapes, ref_notes = outline_shapes(reference)
    if notes or ref_notes:
        return [Issue("layer", "", "shared or scaled shape, kept")]
    targets = [(p, i, s, c) for p, s in own for i, c in enumerate(s.contours)]
    originals = [c for _, s in ref_shapes for c in s.contours]
    if len(targets) != len(originals) or any(int(t[3].nodesCount) != int(o.nodesCount)
                                             for t, o in zip(targets, originals, strict=True)):  # fmt: skip
        return [Issue("layer", "", "incompatible contour or node counts, kept")]
    chosen = [any(n.selected for n in o.nodes()) for o in originals]
    rows = []
    for ci, ((position, index, shape, contour), original) in enumerate(zip(targets, originals, strict=True)):
        if any(chosen) and not chosen[ci]:
            continue
        if contour.isTT or not contour.closed or original.isTT or not original.closed:
            rows.append(Issue(f"contour {ci + 1}", "", OPEN_TT_NOTE))
            continue
        if [n.isOn() for n in contour.nodes()] != [n.isOn() for n in original.nodes()]:
            rows.append(Issue(f"contour {ci + 1}", "", "incompatible point types, kept"))
            continue
        nodes, points = list(contour.nodes()), node_points(contour)
        ends = [i for i, n in enumerate(nodes) if n.isOn()]
        wanted = 2 if mode == "curve" else 4
        picked = [ends[(k + 1) % len(ends)] for k, span in enumerate(spans(original)) if len(span) == wanted]
        if not picked:
            continue
        delta = 2 if mode == "curve" else -2
        rows.append(Issue(f"contour {ci + 1}", str(len(picked)), mode,
                          (contour, [nodes[i] for i in picked], int(contour.nodesCount) + len(picked) * delta),
                          key=(ci, tuple(picked)),
                          after=after(position, index, converted(points, picked, mode), shape)))  # fmt: skip
    return rows


def converted(points: list, picked: list[int], mode: str) -> list:
    """Ghost points: a line gains handles at its thirds; a curve loses both handles."""
    count = len(points)
    if mode == "line":
        return dropped(points, {(p - k) % count for p in picked for k in (1, 2)})
    result = []
    for i, (x, y, on) in enumerate(points):
        if i in picked:
            px, py, _ = points[i - 1]
            result += [(px + (x - px) / 3, py + (y - py) / 3, False),
                       (px + 2 * (x - px) / 3, py + 2 * (y - py) / 3, False)]  # fmt: skip
        result.append((x, y, on))
    return result


def plan_curve_all(layer: Any, options: Mapping[str, Any], context: Context) -> list[Issue]:
    return convert_plan(layer, context.reference, "curve")


def plan_straighten_all(layer: Any, options: Mapping[str, Any], context: Context) -> list[Issue]:
    return convert_plan(layer, context.reference, "line")


def write_curves(layer: Any, edits: list, options: Mapping[str, Any]) -> None:
    for contour, ends, _ in edits:
        for node in ends:
            if node.convertToCurve(False) is False:
                raise RuntimeError("FontLab refused segment conversion.")
        for node in contour.nodes():
            if node.isOn():
                node.smooth = True


def verify_curves(layer: Any, edits: list) -> list[str]:
    found = verify_counts(layer, edits)
    if any(not n.smooth for e in edits for n in e[0].nodes() if n.isOn()):
        found.append(f"{layer.name}: a node is not smooth")
    return found


# Retract Handles ---------------------------------------------------------------
def retractions(contour: Any, selected_only: bool, selected: set[int] | None) -> list[tuple[Any, float, float]]:
    if contour.isTT:
        return []
    nodes = list(contour.nodes())
    ends = [i for i, node in enumerate(nodes) if node.isOn()]
    pairs = list(zip(ends, ends[1:], strict=False))
    if contour.closed and ends:
        pairs.append((ends[-1], ends[0] + len(nodes)))
    result = []
    for start, stop in pairs:
        if stop - start != 3:
            continue
        for handle_index, base_index in ((start + 1, start), (stop - 1, stop)):
            handle, base = nodes[handle_index % len(nodes)], nodes[base_index % len(nodes)]
            if selected_only and not (base.selected if selected is None else base_index % len(nodes) in selected):
                continue
            if (handle.x, handle.y) != (base.x, base.y):
                result.append((handle, float(base.x), float(base.y)))
    return result


def plan_retract(layer: Any, options: Mapping[str, Any], context: Context) -> list[Issue]:
    selected_only, reference = bool(options["selected"]), context.reference
    shapes, notes = outline_shapes(layer)
    originals = [c for _, s in outline_shapes(reference)[0] for c in s.contours] if reference is not None else []
    rows, number = [], 0
    for position, shape in shapes:
        for index, contour in enumerate(shape.contours):
            indices = None
            if selected_only and reference is not None:
                if number >= len(originals) or [n.isOn() for n in originals[number].nodes()] != [
                    n.isOn() for n in contour.nodes()
                ]:
                    return [Issue("nodes", "", "", problem="Master node structures differ.")]
                indices = {i for i, node in enumerate(originals[number].nodes()) if node.selected}
            number += 1
            targets = retractions(contour, selected_only, indices)
            if targets:
                nodes = list(contour.nodes())
                moved = {nodes.index(n): (x, y) for n, x, y in targets}
                rows.append(Issue("handles", str(len(targets)), "retracted", targets,
                                  after=after(position, index, replaced(node_points(contour), moved), shape),
                                  marks=tuple((number - 1, i) for i in moved)))  # fmt: skip
    return rows + note_rows(notes)


# Round Coordinates -------------------------------------------------------------
def snap(value: float, grid: float) -> float:
    return float(math.floor(value / grid + 0.5) * grid) + 0.0


def plan_round(layer: Any, options: Mapping[str, Any], context: Context) -> list[Issue]:
    grid = float(options["grid"])
    if not math.isfinite(grid) or grid < 1:
        raise ValueError("The grid must be 1 unit or more.")
    anchor_edits = []
    if options["anchors"]:
        names = [str(pin.name) for pin in layer.anchors]
        repeated = sorted({n for n in names if names.count(n) > 1})
        if repeated:
            return [Issue("anchors", "", f"several anchors named {', '.join(repeated)}; layer kept")]
        for index, pin in enumerate(layer.anchors):
            old = (float(pin.point.x()), float(pin.point.y()))
            new = (snap(old[0], grid), snap(old[1], grid))
            if old == new:
                continue
            if new == (0.0, 0.0):
                return [Issue("anchors", "", "anchor would move to 0, 0; layer kept (fl#8527)")]
            anchor_edits.append((index, str(pin.name), new))
    shapes, notes = outline_shapes(layer)
    moves, ghosts = [], ()
    for position, shape in shapes:
        dx, dy = translation(shape) or (0.0, 0.0)
        if abs(snap(dx, 1) - dx) > EPSILON or abs(snap(dy, 1) - dy) > EPSILON:
            notes.append("fractional shape offset, kept")
            continue
        for index, contour in enumerate(shape.contours):
            changed = {}
            for i, node in enumerate(contour.nodes()):
                x, y = float(node.x), float(node.y)
                nx, ny = snap(x + dx, grid) - dx, snap(y + dy, grid) - dy
                if abs(nx - x) > EPSILON or abs(ny - y) > EPSILON:
                    moves.append((node, nx, ny))
                    changed[i] = (nx, ny)
            if changed:
                ghosts += after(position, index, replaced(node_points(contour), changed), shape)
    rows = []
    if moves:
        rows.append(Issue("nodes", f"{len(moves)} off grid", f"on grid {fmt(grid)}", ("nodes", moves), after=ghosts))
    for shape in layer.shapes if options["offsets"] else ():
        if not shape.isComponent:
            continue
        old = (float(shape.transform.dx()), float(shape.transform.dy()))
        new = (snap(old[0], grid), snap(old[1], grid))
        if any(abs(new[i] - old[i]) > EPSILON for i in (0, 1)):
            rows.append(Issue(str(shape.shapeData.componentGlyph), f"{fmt(old[0])}, {fmt(old[1])}",
                              f"{fmt(new[0])}, {fmt(new[1])}", ("offset", shape, new)))  # fmt: skip
    if anchor_edits:
        rows.append(Issue("anchors", f"{len(anchor_edits)} off grid", f"on grid {fmt(grid)}", ("anchors", anchor_edits)))
    return rows + note_rows(notes)


def write_round(layer: Any, edits: list, options: Mapping[str, Any]) -> None:
    from PythonQt import QtCore, QtGui

    pins = list(layer.anchors)
    for kind, *payload in edits:
        if kind == "nodes":
            for node, x, y in payload[0]:
                node.x, node.y = x, y
        elif kind == "anchors":
            for index, _, (x, y) in payload[0]:
                pins[index].point = QtCore.QPointF(x, y)
        else:
            shape, (dx, dy) = payload
            m = shape.transform
            shape.transform = QtGui.QTransform(m.m11(), m.m12(), m.m21(), m.m22(), dx, dy)
            shape.changed()


def verify_round(layer: Any, edits: list) -> list[str]:
    missed, pins = [], list(layer.anchors)
    for kind, *payload in edits:
        if kind == "nodes":
            wrong = [1 for node, x, y in payload[0] if abs(node.x - x) > 0.01 or abs(node.y - y) > 0.01]
            if wrong:
                missed.append(f"{layer.name}: {plural(len(wrong), 'node')}")
        elif kind == "anchors":
            missed += [f"{layer.name}/{name}" for index, name, (x, y) in payload[0]
                       if (float(pins[index].point.x()), float(pins[index].point.y())) != (x, y)]  # fmt: skip
        else:
            shape, (dx, dy) = payload
            if abs(shape.transform.dx() - dx) > 0.01 or abs(shape.transform.dy() - dy) > 0.01:
                missed.append(f"{layer.name}: {shape.shapeData.componentGlyph} offset")
    return missed


# Remove Overlap ----------------------------------------------------------------
def start_points(shape: Any) -> set[tuple[float, float]]:
    found = set()
    for contour in shape.contours:
        points = node_points(contour)
        if points and points[0][2]:
            found.add((round(points[0][0], 3), round(points[0][1], 3)))
    return found


def plan_overlap(layer: Any, options: Mapping[str, Any], context: Context, *, fontgate: Any = None) -> list[Issue]:
    shapes, notes = outline_shapes(layer)
    rows = []
    for index, (position, shape) in enumerate(shapes):
        if translation(shape) != (0.0, 0.0):
            notes.append("moved shape, kept")
            continue
        items = list(shape.contours)
        if any(not contour.closed for contour in items):
            notes.append(OPEN_NOTE)
            continue
        if not any(a.hasIntersPoints(b) or (a.clockwise == b.clockwise and (a.contains(b) or b.contains(a)))
                   for i, a in enumerate(items) for b in items[i + 1 :]):  # fmt: skip
            continue
        before = tuple(sorted(int(c.nodesCount) for c in items))
        result = outline.merged_copy(shape, fontgate=fontgate)
        counts = outline.node_counts(result)
        rows.append(Issue(f"shape {index + 1}", plural(len(before), "contour"), plural(len(counts), "contour"),
                          (shape, result, start_points(shape), len(counts), final_smooth_points(items)),
                          key=(index, len(counts), counts),
                          marks=tuple((position, i) for i in range(len(items)))))  # fmt: skip
    return rows + note_rows(notes)


def write_overlap(layer: Any, edits: list, options: Mapping[str, Any]) -> None:
    for shape, result, starts, *_ in edits:
        shape.assign(result)
        for contour in shape.contours:
            for index, (x, y, on) in enumerate(node_points(contour)):
                if index and on and (round(x, 3), round(y, 3)) in starts:
                    contour.setStartPoint(index)
                    break
        shape.changed()


def verify_overlap(layer: Any, edits: list) -> list[str]:
    return [f"{layer.name}: {len(list(s.contours))} of {n} contours" for s, _, _, n, _ in edits
            if len(list(s.contours)) != n]  # fmt: skip


def final_smooth_points(contours: Any) -> set[tuple[float, float]]:
    """Coordinates of final off-curves of closed contours with raw Smooth (fl#8517); read only."""
    result = set()
    for contour in contours:
        nodes = list(contour.nodes())
        if contour.closed and nodes and not nodes[-1].isOn() and nodes[-1].smooth:
            result.add((float(nodes[-1].x), float(nodes[-1].y)))
    return result


def advise_overlap(layer: Any, edits: list) -> list[str]:
    """Remove Overlap's save-risk advice: a raw-Smooth final off-curve the merge introduced (fl#8517)."""
    for shape, _, _, _, before in edits:
        if final_smooth_points(shape.contours) - before:
            return [f"{layer.name}: a final off-curve with raw Smooth was introduced; FontLab may change on save "
                    "(fl#8517). Check node types after VFJ reopen."]  # fmt: skip
    return []
