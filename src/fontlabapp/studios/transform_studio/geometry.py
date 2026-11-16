# this_file: src/fontlabapp/studios/transform_studio/geometry.py
# SPDX-License-Identifier: Apache-2.0
"""Qt-free outline snapshots, affine maths, edit simulation and the ghost overlay.

What: ``Layer``/``Shape``/``Contour``/``Node`` are read-only snapshots of one
native layer (``native.snapshot``). Planners turn a snapshot into ``Change``
rows whose ``edit`` is a tuple of steps:

* ``("shape", shape, matrix, bake)`` sets a shape transform; ``bake`` folds it
  into the nodes (own outlines), otherwise it stays (components).
* ``("node", shape, contour, node, x, y, smooth)`` moves one node (shape-local
  coordinates; ``smooth`` None keeps it).
* ``("remove", shape, contour, indices, count)`` deletes nodes.
* ``("anchor", index, x, y)`` and ``("advance", width)``.

``simulate`` applies steps to a snapshot and ``ghost`` draws the result as a
TGlyph overlay; ``verify`` compares a read-back snapshot with the plan.
Why: the Studio boundary forbids importing ``fontlabapp.contours``; this
module privately repeats its affine contract (``a, b, c, d, e, f`` =
``QTransform(m11, m12, m21, m22, dx, dy)``). Shared by Transform Studio and
Align & Nudge (``fontlabapp.studios.align_nudge``).
"""

import math
from collections.abc import Iterable, Sequence
from typing import NamedTuple

Affine = tuple[float, float, float, float, float, float]
IDENTITY: Affine = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
EPS = 1e-9
NODE_TOLERANCE = 0.5
MATRIX_TOLERANCE = 1e-6
ORIGIN_ERROR = ("{names} would move to 0, 0; FontLab cannot redo that (fl#8527). "
                "Untick the anchors or change the values.")  # fmt: skip


class Node(NamedTuple):
    x: float
    y: float
    on: bool = True
    smooth: bool = False
    selected: bool = False


class Contour(NamedTuple):
    nodes: tuple[Node, ...]
    closed: bool = True
    tt: bool = False
    matrix: Affine = IDENTITY


class Shape(NamedTuple):
    matrix: Affine = IDENTITY
    contours: tuple[Contour, ...] = ()
    component: bool = False
    locked: bool = False
    shared: bool = False
    selected: bool = False
    box: tuple[float, float, float, float] | None = (
        None  # local x0, y0, x1, y1 (components)
    )
    linked: bool = False  # raw element sharing (component users too): bake and ownership rule


class Layer(NamedTuple):
    shapes: tuple[Shape, ...] = ()
    anchors: tuple[tuple[str, float, float], ...] = ()
    advance: float = 0.0
    locked: bool = False
    body: bool = True  # False for mask and service layers


class Change(NamedTuple):
    """One table row: ``edit`` is a tuple of steps (None for a report row)."""

    name: str
    old: str
    new: str
    edit: tuple | None = None
    problem: str = ""
    key: tuple | None = None


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


# Affine ------------------------------------------------------------------
def finite(*values: float) -> bool:
    return all(math.isfinite(v) for v in values)


def concat(first: Affine, then: Affine) -> Affine:
    """``first`` followed by ``then`` (Qt ``first * then``)."""
    a, b, c, d, e, f = first
    A, B, C, D, E, F = then
    return (
        a * A + b * C,
        a * B + b * D,
        c * A + d * C,
        c * B + d * D,
        e * A + f * C + E,
        e * B + f * D + F,
    )


def apply(m: Affine, x: float, y: float) -> tuple[float, float]:
    return (m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5])


def invert(m: Affine) -> Affine:
    a, b, c, d, e, f = m
    det = a * d - b * c
    if abs(det) < 1e-12:
        raise ValueError("The transform is not invertible.")
    ia, ib, ic, id_ = d / det, -b / det, -c / det, a / det
    return (ia, ib, ic, id_, -(e * ia + f * ic), -(e * ib + f * id_))


def translate(dx: float, dy: float) -> Affine:
    return (1.0, 0.0, 0.0, 1.0, float(dx), float(dy))


def rotation(degrees: float) -> Affine:
    r = math.radians(degrees)
    return (math.cos(r), math.sin(r), -math.sin(r), math.cos(r), 0.0, 0.0)


def about(linear: Affine, ox: float, oy: float) -> Affine:
    """``linear`` applied around the point ``(ox, oy)``."""
    return concat(concat(translate(-ox, -oy), linear), translate(ox, oy))


def is_identity(m: Affine) -> bool:
    return all(abs(v - w) <= EPS for v, w in zip(m, IDENTITY))


def is_translation(m: Affine) -> bool:
    return (
        abs(m[0] - 1) < EPS
        and abs(m[3] - 1) < EPS
        and abs(m[1]) < EPS
        and abs(m[2]) < EPS
    )


# Snapshot reading --------------------------------------------------------
def glyph_points(shape: Shape) -> list[tuple[float, float]]:
    """Every node of ``shape`` in glyph space."""
    return [
        apply(shape.matrix, n.x, n.y)
        for contour in shape.contours
        for n in contour.nodes
    ]


def corners(shape: Shape) -> list[tuple[float, float]]:
    if shape.box is None:
        return []
    x0, y0, x1, y1 = shape.box
    return [
        apply(shape.matrix, x, y) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    ]


def _cubic_extrema(p0: float, p1: float, p2: float, p3: float) -> list[float]:
    a, b, c = -p0 + 3 * p1 - 3 * p2 + p3, 2 * (p0 - 2 * p1 + p2), p1 - p0
    if abs(a) < 1e-12:
        roots = [-c / b] if abs(b) > 1e-12 else []
    else:
        disc = b * b - 4 * a * c
        roots = (
            [] if disc < 0 else [(-b + s * math.sqrt(disc)) / (2 * a) for s in (1, -1)]
        )
    out = []
    for t in roots:
        if 0 < t < 1:
            u = 1 - t
            out.append(u**3 * p0 + 3 * u * u * t * p1 + 3 * u * t * t * p2 + t**3 * p3)
    return out


def _quad_extrema(p0: float, p1: float, p2: float) -> list[float]:
    den = p0 - 2 * p1 + p2
    if abs(den) < 1e-12:
        return []
    t = (p0 - p1) / den
    return [(1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t * t * p2] if 0 < t < 1 else []


def ink_box(
    contours: Iterable[Sequence[tuple[float, float, bool]]],
) -> tuple[float, float, float, float] | None:
    """Exact ``(x, y, w, h)`` of cubic/quadratic contours given as ``(x, y, on)`` lists in glyph space."""
    xs: list[float] = []
    ys: list[float] = []
    for points in contours:
        ons = [i for i, p in enumerate(points) if p[2]]
        xs += [points[i][0] for i in ons]
        ys += [points[i][1] for i in ons]
        n = len(points)
        for k, start in enumerate(ons):
            end = ons[(k + 1) % len(ons)]
            offs = [points[(start + j) % n] for j in range(1, (end - start) % n or n)]
            ends = (points[start], points[end])
            if len(offs) == 2:
                xs += _cubic_extrema(ends[0][0], offs[0][0], offs[1][0], ends[1][0])
                ys += _cubic_extrema(ends[0][1], offs[0][1], offs[1][1], ends[1][1])
            elif len(offs) == 1:
                xs += _quad_extrema(ends[0][0], offs[0][0], ends[1][0])
                ys += _quad_extrema(ends[0][1], offs[0][1], ends[1][1])
    if not xs:
        return None
    return (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))


def layer_ink(
    layer: Layer, extra: Affine = IDENTITY
) -> tuple[float, float, float, float] | None:
    """Ink box of the layer's own outlines after ``extra`` (components excluded)."""
    rings = []
    for shape in layer.shapes:
        m = concat(shape.matrix, extra)
        for contour in shape.contours:
            rings.append([(*apply(m, n.x, n.y), n.on) for n in contour.nodes])
    return ink_box(rings)


def subject(names: Sequence[str]) -> str:
    unique = list(dict.fromkeys(names))
    return unique[0] if len(unique) == 1 else f"{len(unique)} glyphs"


def plural(count: int, word: str) -> str:
    return f"{count} {word}" + ("" if count == 1 else "s")


# Whole-layer transforms --------------------------------------------------
def anchor_steps(layer: Layer, matrix: Affine) -> tuple[list[tuple], str]:
    """Anchor moves under ``matrix`` and the fl#8527 problem text (or "")."""
    steps, stuck = [], []
    for index, (name, x, y) in enumerate(layer.anchors):
        nx, ny = apply(matrix, x, y)
        if abs(nx - x) <= EPS and abs(ny - y) <= EPS:
            continue
        if math.hypot(nx, ny) < NODE_TOLERANCE and (x, y) != (0, 0):
            stuck.append(name)
        steps.append(("anchor", index, nx, ny))
    return steps, (ORIGIN_ERROR.format(names=", ".join(stuck)) if stuck else "")


def transform_changes(
    layer: Layer, matrix: Affine, anchors: bool, note: str, *, bake_only: bool = False
) -> list[Change]:
    """Rows for ``matrix`` applied to every shape (and optionally anchors) of ``layer``.

    FontLab's layer-transform rule, as in ``fontlabapp.contours.transform``:
    an own, unshared outline whose transform only moves is baked (new node
    positions); every other shape (components, shared outlines, scaled or
    rotated own outlines) keeps its nodes and gets the composed shape
    transform, so the whole glyph moves together. With ``bake_only``
    (Smart Slant) components are skipped; its caller refuses them first.
    """
    if not finite(*matrix):
        raise ValueError("Non-finite transform; all values must be finite.")
    if is_identity(matrix):
        return []
    steps, nodes = [], 0
    for index, shape in enumerate(layer.shapes):
        if shape.component:
            if not bake_only:
                steps.append(("shape", index, concat(shape.matrix, matrix), False))
            continue
        if not shape.contours:
            continue
        bake = not (shape.shared or shape.linked) and is_translation(shape.matrix)  # raw count: baking rewrites shared element data
        steps.append(("shape", index, concat(shape.matrix, matrix), bake))
        nodes += sum(len(c.nodes) for c in shape.contours)
    rows: list[Change] = []
    problem = ""
    if anchors:
        moves, problem = anchor_steps(layer, matrix)
        steps += moves
    if steps:
        components = sum(1 for s in steps if s[0] == "shape" and not s[3])
        old = plural(nodes, "node") + (
            f", {plural(components, 'component')}" if components else ""
        )
        rows.insert(0, Change("outline", old, note, tuple(steps), problem))
    return rows


# Simulation, ghost and read-back ------------------------------------------
def simulate(layer: Layer, steps: Iterable[tuple]) -> Layer:
    """The snapshot ``layer`` after ``steps`` (baked shapes get an identity transform)."""
    shapes = [list(shape) for shape in layer.shapes]
    nodes = {
        (s, c): list(contour.nodes)
        for s, shape in enumerate(layer.shapes)
        for c, contour in enumerate(shape.contours)
    }
    anchors, advance = list(layer.anchors), layer.advance
    removals = []
    for step in steps:
        kind = step[0]
        if kind == "shape":
            _, s, matrix, bake = step
            if bake:
                for c, _contour in enumerate(layer.shapes[s].contours):
                    nodes[s, c] = [n._replace(x=apply(matrix, n.x, n.y)[0], y=apply(matrix, n.x, n.y)[1])
                                   for n in nodes[s, c]]  # fmt: skip
                matrix = IDENTITY
            shapes[s][0] = matrix
        elif kind == "node":
            _, s, c, i, x, y, smooth = step
            old = nodes[s, c][i]
            nodes[s, c][i] = old._replace(
                x=x, y=y, smooth=old.smooth if smooth is None else smooth
            )
        elif kind == "remove":
            removals.append(step)
        elif kind == "anchor":
            name = anchors[step[1]][0]
            anchors[step[1]] = (name, step[2], step[3])
        else:
            advance = step[1]
    for _, s, c, indices, _count in removals:
        for i in sorted(indices, reverse=True):
            del nodes[s, c][i]
    built = []
    for s, shape in enumerate(layer.shapes):
        contours = tuple(
            contour._replace(nodes=tuple(nodes[s, c]))
            for c, contour in enumerate(shape.contours)
        )
        built.append(Shape(shapes[s][0], contours, *shape[2:]))
    return layer._replace(shapes=tuple(built), anchors=tuple(anchors), advance=advance)


def ghost(layer: Layer) -> Overlay:
    """The layer's own outlines in glyph space as a TGlyph overlay (components are not drawn)."""
    contours = []
    for shape in layer.shapes:
        if shape.component:
            continue
        for contour in shape.contours:
            m = concat(contour.matrix, shape.matrix)
            points = tuple(
                OverlayPoint(*apply(m, n.x, n.y), "line" if n.on else None, n.smooth)
                for n in contour.nodes
            )
            contours.append(OverlayContour(points, contour.closed))
    return Overlay(tuple(contours))


def verify(
    label: str, expected: Layer, actual: Layer, steps: Sequence[tuple]
) -> list[str]:
    """Read-back problems: nodes and anchors beyond 0.5 unit, transforms beyond 1e-6, wrong counts."""
    problems = []
    touched = {step[1] for step in steps if step[0] in ("shape", "node", "remove")}
    for s in sorted(touched):
        want, got = (
            expected.shapes[s],
            actual.shapes[s] if s < len(actual.shapes) else None,
        )
        if got is None or [len(c.nodes) for c in want.contours] != [
            len(c.nodes) for c in got.contours
        ]:
            problems.append(f"{label}: the node count differs from the plan")
            continue
        if (
            want.component
            and max(abs(p - q) for p, q in zip(want.matrix, got.matrix))
            > MATRIX_TOLERANCE
        ):
            problems.append(f"{label}: component placement differs")
        far = [
            1
            for p, q in zip(glyph_points(want), glyph_points(got))
            if math.dist(p, q) > NODE_TOLERANCE
        ]
        smooth = [1 for cw, cg in zip(want.contours, got.contours) for nw, ng in zip(cw.nodes, cg.nodes)
                  if nw.smooth != ng.smooth]  # fmt: skip
        if far or smooth:
            problems.append(f"{label}: a node differs from the plan")
    for step in steps:
        if step[0] == "anchor":
            _, x, y = (
                actual.anchors[step[1]]
                if step[1] < len(actual.anchors)
                else ("", math.inf, math.inf)
            )
            if math.dist((x, y), (step[2], step[3])) > NODE_TOLERANCE:
                problems.append(
                    f"{label}: anchor {expected.anchors[step[1]][0]} is at {x:g}, {y:g}"
                )
        elif step[0] == "advance" and abs(actual.advance - step[1]) > NODE_TOLERANCE:
            problems.append(f"{label}: advance is {actual.advance:g}, not {step[1]:g}")
    return problems
