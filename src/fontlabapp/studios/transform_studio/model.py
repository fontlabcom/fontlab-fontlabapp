# this_file: src/fontlabapp/studios/transform_studio/model.py
# SPDX-License-Identifier: Apache-2.0
"""Transform Studio planners: Transform, Slant, Smart Slant and selection rotate/reflect.

What: pure functions over ``geometry.Layer`` snapshots that keep the controls,
defaults, messages and maths of the Scriptmix ``Outline Transform``, ``Slant``,
``Smart Slant``, ``Rotate Selection`` and ``Reflect Selection H/V`` scripts.
Each returns ``geometry.Change`` rows (or a skip note string).
Why: the planning is testable without FontLab; ``session`` reads and writes.
"""

import math
from collections.abc import Sequence

from .geometry import (
    IDENTITY,
    Affine,
    Change,
    Layer,
    about,
    apply,
    concat,
    corners,
    finite,
    invert,
    is_identity,
    layer_ink,
    rotation,
    transform_changes,
    translate,
)

ORIGINS = (
    "Bounding box centre",
    "Bounding box bottom-left",
    "Glyph origin (0, 0)",
    "Advance centre on baseline",
)
PIVOTS = ("Baseline", "Half x-height (keeps the glyph centred)")
SCALE_RANGE = (1.0, 1000.0)
SKEW_RANGE = (-80.0, 80.0)
ROTATE_RANGE = (-360.0, 360.0)
MOVE_RANGE = (-5000.0, 5000.0)
SLANT_RANGE = (-45.0, 45.0)
SMART_RANGE = (-80.0, 80.0)
SLANT_DEFAULT = 10.0
ROTATE_DEFAULT = 10.0
PRESETS = (1, 10, 45)
FLATTEN_ERROR = "A scale of 0 % would flatten the outline."
SLANT_ERROR = "The angle must be between -89° and 89°."
SMART_ERROR = "Choose an angle between -80° and 80°."
FINITE_ANGLE = "Enter a finite angle."
REFLECTIONS = {
    "horizontal": (-1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
    "vertical": (1.0, 0.0, 0.0, -1.0, 0.0, 0.0),
}
EMPTY_NOTE = "empty layer, skipped"


# Transform ---------------------------------------------------------------
def linear(sx: float, sy: float, skew: float, rotate: float) -> Affine:
    """Scale (percent), then skew (degrees), then rotate (degrees, CCW)."""
    if not finite(sx, sy, skew, rotate):
        raise ValueError("Non-finite transform; all values must be finite.")
    if sx == 0 or sy == 0:
        raise ValueError(FLATTEN_ERROR)
    m = (sx / 100.0, 0.0, 0.0, sy / 100.0, 0.0, 0.0)
    m = concat(m, (1.0, 0.0, math.tan(math.radians(skew)), 1.0, 0.0, 0.0))
    return concat(m, rotation(rotate))


def layer_box(layer: Layer) -> tuple[float, float, float, float] | None:
    """``(x, y, w, h)`` of the own outlines and component boxes, like ``layer.boundingBox``."""
    ink = layer_ink(layer)
    points = [p for shape in layer.shapes if shape.component for p in corners(shape)]
    if ink is not None:
        x, y, w, h = ink
        points += [(x, y), (x + w, y + h)]
    if not points:
        return None
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))


def origin_of(layer: Layer, choice: int) -> tuple[float, float] | None:
    """The transform origin for ``ORIGINS[choice]``; None when a box is needed but the layer is empty."""
    if choice == 2:
        return (0.0, 0.0)
    if choice == 3:
        return (layer.advance / 2.0, 0.0)
    box = layer_box(layer)
    if box is None:
        return None
    x, y, w, h = box
    return (x + w / 2.0, y + h / 2.0) if choice == 0 else (x, y)


def mapper(
    lin: Affine, origin: tuple[float, float], move: tuple[float, float]
) -> Affine:
    """``lin`` around ``origin``, then the move."""
    return concat(about(lin, *origin), translate(*move))


def transform_planner_changes(
    layer: Layer, lin: Affine, choice: int, move: tuple[float, float], anchors: bool
) -> list[Change] | str:
    origin = origin_of(layer, choice)
    if origin is None:
        return EMPTY_NOTE
    matrix = mapper(lin, origin, move)
    return transform_changes(
        layer, matrix, anchors, f"origin {origin[0]:g}, {origin[1]:g}"
    )


# Slant ----------------------------------------------------------------------
def slant_matrix(angle: float, pivot_y: float) -> Affine:
    if not finite(angle, pivot_y) or not -89 < angle < 89:
        raise ValueError(SLANT_ERROR)
    k = math.tan(math.radians(angle))
    return (1.0, 0.0, k, 1.0, -k * pivot_y, 0.0)


def slant_changes(
    layer: Layer, angle: float, pivot_y: float, anchors: bool
) -> list[Change]:
    return transform_changes(
        layer,
        slant_matrix(angle, pivot_y),
        anchors,
        f"slant {angle:g}° at y {pivot_y:g}",
    )


def smart_check(angle: float) -> None:
    if not finite(angle) or not SMART_RANGE[0] <= angle <= SMART_RANGE[1]:
        raise ValueError(SMART_ERROR)


def smart_changes(
    layer: Layer, angle: float, sidebearings: bool, anchors: bool
) -> list[Change] | str:
    """Smart Slant: shear about a third of the ink height, then keep sidebearings or the ink centre."""
    smart_check(angle)
    if layer.locked:
        return "locked layer, kept"
    for shape in layer.shapes:
        # ``linked`` (raw count) on purpose: Smart Slant only bakes, and baking rewrites shared element data.
        if shape.component or shape.locked or shape.shared or shape.linked:
            return "component, locked or linked outline, kept"
        if any(not c.closed for c in shape.contours):
            return "open contour, kept"
        if any(not is_identity(c.matrix) for c in shape.contours):
            return "contour transform, kept"
    before = layer_ink(layer)
    if before is None or angle == 0:
        return []
    x, y, w, h = before
    if w <= 0 or h <= 0:
        return "zero ink width or height, kept"
    k = math.tan(math.radians(angle))
    shear = (1.0, 0.0, k, 1.0, -k * (y + h / 3.0), 0.0)
    after = layer_ink(layer, shear)
    ax, _, aw, _ = after  # type: ignore[misc]
    dx = x - ax if sidebearings else (x + w / 2.0) - (ax + aw / 2.0)
    matrix = concat(shear, translate(dx, 0))
    advance = layer.advance + aw - w if sidebearings else layer.advance
    if not math.isfinite(advance) or advance < 0:
        return "negative or non-finite advance, kept"
    rows = transform_changes(
        layer, matrix, anchors, f"slant {angle:g}°, shift {dx:+.1f}", bake_only=True
    )
    if any(row.problem for row in rows):
        return "; ".join(row.problem for row in rows if row.problem) + "; kept"
    if abs(advance - layer.advance) > 1e-9:
        rows.append(Change("advance", f"{layer.advance:g}", f"{advance:g}", (("advance", advance),)))
    return rows


# Selection rotate and reflect ---------------------------------------------
def selection_matrix(lin: Affine, origin: tuple[float, float]) -> Affine:
    if not finite(*lin):
        raise ValueError(FINITE_ANGLE)
    return about(lin, *origin)


def _selection_problem(
    layer: Layer,
    shape_locked: bool,
    shared: bool,
    contour_matrix: Affine,
    points: Sequence[tuple],
) -> str:
    if not finite(*(v for p in points for v in p)):
        return "Selected contour has non-finite coordinates."
    if layer.locked or shape_locked:
        return "Unlock the selected layer and shape first."
    if shared:
        return "Selected outline data is shared; unlink it first."
    if not is_identity(contour_matrix):
        return "Bake the selected contour transform first."
    return ""


def selection_changes(layer: Layer, lin: Affine) -> list[Change]:
    """Rotate or reflect the selected nodes and components about the selection centre."""
    entries, components = [], []
    for s, shape in enumerate(layer.shapes):
        if shape.component:
            if shape.selected:
                if layer.locked or shape.locked:
                    return [
                        Change(
                            "selected geometry",
                            "",
                            "",
                            problem="Unlock the selected layer and component first.",
                        )
                    ]
                components.append(s)
            continue
        for c, contour in enumerate(shape.contours):
            if not any(n.selected for n in contour.nodes):
                continue
            problem = _selection_problem(
                layer,
                shape.locked,
                shape.shared,
                contour.matrix,
                [(n.x, n.y) for n in contour.nodes],
            )
            if problem:
                return [Change("selected geometry", "", "", problem=problem)]
            entries += [(s, c, i, n) for i, n in enumerate(contour.nodes) if n.selected]
    points = [apply(layer.shapes[s].matrix, n.x, n.y) for s, _, _, n in entries]
    points += [p for s in components for p in corners(layer.shapes[s])]
    if not points:
        return []
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    centre = ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)
    matrix = selection_matrix(lin, centre)
    steps = []
    for s, c, i, node in entries:
        shape = layer.shapes[s].matrix
        x, y = apply(invert(shape), *apply(matrix, *apply(shape, node.x, node.y)))
        if abs(x - node.x) > 1e-8 or abs(y - node.y) > 1e-8:
            steps.append(("node", s, c, i, x, y, None))
    if matrix != IDENTITY:
        steps += [
            ("shape", s, concat(layer.shapes[s].matrix, matrix), False)
            for s in components
        ]
    if not steps:
        return []
    return [Change("selected geometry", f"{len(entries)} nodes, {len(components)} components",
                   f"centre {centre[0]:g}, {centre[1]:g}", tuple(steps))]  # fmt: skip


def rotation_linear(angle: float) -> Affine:
    """The linear part of a counter-clockwise rotation by ``angle`` degrees (Rotate Selection)."""
    if not finite(angle):
        raise ValueError(FINITE_ANGLE)
    return rotation(angle)
