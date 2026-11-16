# this_file: src/fontlabapp/studios/_contours.py
# SPDX-License-Identifier: Apache-2.0
"""Shared contour helpers for the studios (Scriptmix TODO:46–47).

What: the contour-selection scaffold that four Scriptmix scripts repeated
(``selected_contours``, the ``NodeEditor`` write/check pair as
``write_moves``/``check_moves`` and ``chosen_masters``), the selection planner
that three of them repeated with only a different linear map
(``selection_matrix``/``selection_changes``/``write_selection``/
``check_selection``) and the five identical ``spans`` helpers.
Why: the studio boundary forbids ``fontlabapp.contours``; studios that edit
selected contours or walk native segments import these instead of copying
them again. Script-specific transforms and controls stay with each caller:
the ``linear`` map is an argument. Used by the Outline Doctor (``spans``) and
by later studios (Issue 242 T20).
"""

import math
from collections.abc import Callable, Iterable, Sequence
from typing import Any

import fontlabapp.core.sharing as sharing

from .transform_studio.geometry import IDENTITY, Affine, Change, apply, concat, invert
from .transform_studio.native import matrix_of

XY = tuple[float, float]
Move = tuple[Any, float, float, bool | None]
Linear = Callable[[float], Affine]
UNDO_HINT = "Native changes may remain; use Edit > Undo."


# TODO:47 — the five ``spans`` helpers ----------------------------------------
def node_spans(nodes: Sequence[Any], is_on: Callable[[Any], bool]) -> list[list[Any]]:
    """Segments of one closed node cycle: each starts and ends on-curve.

    Raises ValueError for any segment that is neither a line (2 nodes) nor a
    cubic (4 nodes), exactly like the five Scriptmix copies.
    """
    nodes = list(nodes)
    ends = [i for i, node in enumerate(nodes) if is_on(node)]
    result = []
    for number, start in enumerate(ends):
        stop = ends[(number + 1) % len(ends)]
        length = (stop - start) % len(nodes) or len(nodes)
        span = [nodes[(start + offset) % len(nodes)] for offset in range(length + 1)]
        if len(span) not in (2, 4):
            raise ValueError("A contour has an unsupported segment structure.")
        result.append(span)
    return result


def spans(contour: Any) -> list[list[Any]]:
    """Native ``flContour`` segments (Make Compatible, Comb, Straighten All Curves,
    Superaligner, Curve All Straights)."""
    if contour.isTT or not contour.closed:
        raise ValueError("Use closed PostScript contours.")
    return node_spans(contour.nodes(), lambda node: bool(node.isOn()))


# TODO:46 — the four contour-selection scaffolds ------------------------------
@sharing.sharing_operation()  # one component-user count for all selected shapes
def selected_contours(layer: Any) -> list[tuple[Any, Any, list[Any]]]:
    """Selected own contours as (shape, contour, nodes); refuse locked or shared outlines."""
    result = []
    for shape in layer.shapes:
        if shape.isComponent:
            continue
        for contour in shape.contours:
            nodes = list(contour.nodes())
            if not any(node.selected for node in nodes):
                continue
            if not all(math.isfinite(float(v)) for n in nodes for v in (n.x, n.y)):
                raise ValueError("Selected contour has non-finite coordinates.")
            if layer.isLocked or shape.contentLocked:
                raise ValueError("Unlock the selected layer and shape first.")
            if sharing.element_shared(shape, layer) or list(shape.includesList):
                raise ValueError("Selected outline data is shared; unlink it first.")
            if matrix_of(contour.transform) != IDENTITY:
                raise ValueError("Bake the selected contour transform first.")
            result.append((shape, contour, nodes))
    return result


def write_moves(moves: Iterable[Move]) -> None:
    """``NodeEditor.write``: assign coordinates on the original node objects."""
    for node, x, y, smooth in moves:
        node.x, node.y = x, y
        if smooth is not None:
            node.smooth = smooth


def check_moves(layer: Any, moves: Iterable[Move]) -> None:
    """``NodeEditor.check``: raise RuntimeError when a node differs after whole-unit rounding."""
    for node, x, y, smooth in moves:
        if (
            not math.isfinite(node.x)
            or not math.isfinite(node.y)
            or abs(node.x - x) > 0.5
            or abs(node.y - y) > 0.5
            or (smooth is not None and bool(node.smooth) != smooth)
        ):
            raise RuntimeError(f"{layer.name}: a node differs from the plan. {UNDO_HINT}")


def chosen_masters(
    masters: Sequence[str],
    all_masters: bool,
    occurrences: Iterable[tuple[Any, str, str]] = (),
    package_id: Any = None,
) -> tuple[list[str], set[tuple[str, str]] | None]:
    """Master names to edit and the selected (glyph, layer) pairs (None when every layer).

    ``occurrences`` are the (package id, glyph, layer) triples a caller captured
    from the editor selection; a triple from another font refuses.
    """
    if all_masters:
        return list(masters), None
    pairs: set[tuple[str, str]] = set()
    for owner, glyph, layer in occurrences:
        if package_id is not None and owner != package_id:
            raise ValueError("Selected layers belong to another font; reload selection.")
        pairs.add((glyph, layer))
    return list(dict.fromkeys(layer for _, layer in sorted(pairs))), pairs


# TODO:46 — the three SelectionEditor/selection_changes planners --------------
def selection_matrix(value: float, centre: XY, linear: Linear) -> Affine:
    """Map glyph coordinates with ``linear(value)`` about ``centre``."""
    if not math.isfinite(value):
        raise ValueError("Enter a finite angle.")
    a, b, c, d, _, _ = matrix = linear(value)
    ox, oy = centre
    return concat(matrix, (1, 0, 0, 1, ox - a * ox - c * oy, oy - b * ox - d * oy))


def selection_changes(layer: Any, value: float, linear: Linear) -> list[Change]:
    """Plan selected nodes and selected component transforms in glyph coordinates."""
    entries, coordinates, components = [], [], []
    for shape, _, nodes in selected_contours(layer):
        forward = matrix_of(shape.transform)
        backward = invert(forward)
        for node in nodes:
            if node.selected:
                point = apply(forward, float(node.x), float(node.y))
                coordinates.append(point)
                entries.append((node, point, backward))
    for shape in layer.shapes:
        if not shape.isComponent or not shape.selected:
            continue
        if layer.isLocked or shape.contentLocked:
            raise ValueError("Unlock the selected layer and component first.")
        box, forward = shape.boundingBox, matrix_of(shape.transform)
        for x in (box.x(), box.x() + box.width()):
            for y in (box.y(), box.y() + box.height()):
                coordinates.append(apply(forward, x, y))
        components.append(shape)
    if not coordinates:
        return []
    xs, ys = zip(*coordinates, strict=True)
    centre = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
    matrix = selection_matrix(value, centre, linear)
    moves = []
    for node, point, backward in entries:
        x, y = apply(backward, *apply(matrix, *point))
        if abs(x - node.x) > 1e-8 or abs(y - node.y) > 1e-8:
            moves.append((node, x, y, None))
    placed = [(shape, concat(matrix_of(shape.transform), matrix))
              for shape in components if matrix != IDENTITY]  # fmt: skip
    if not moves and not placed:
        return []
    return [Change("selected geometry", f"{len(entries)} nodes, {len(components)} components",
                   f"centre {centre[0]:g}, {centre[1]:g}", (moves, placed))]  # fmt: skip


def write_selection(steps: Iterable[tuple[list[Move], list[tuple[Any, Affine]]]]) -> None:
    """``SelectionEditor.write``: node moves, then whole component matrices."""
    from PythonQt import QtGui

    for moves, placed in steps:
        write_moves(moves)
        for shape, matrix in placed:
            shape.transform = QtGui.QTransform(*matrix)
            shape.changed()


def check_selection(layer: Any, steps: Iterable[tuple[list[Move], list[tuple[Any, Affine]]]]) -> None:
    """``SelectionEditor.check``: read every moved node and component matrix back."""
    for moves, placed in steps:
        check_moves(layer, moves)
        for shape, matrix in placed:
            now = matrix_of(shape.transform)
            if any(abs(a - b) > 1e-6 for a, b in zip(now, matrix, strict=True)):
                raise RuntimeError(f"Component placement differs. {UNDO_HINT}")
