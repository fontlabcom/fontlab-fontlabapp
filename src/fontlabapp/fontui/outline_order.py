# this_file: src/fontlabapp/fontui/outline_order.py
# SPDX-License-Identifier: Apache-2.0
"""Exact direction and start-point strategies moved from Scriptmix into App.

Uses native midpoint containment, cross-shape ambiguity holds and original
raw-Smooth save-risk advice. Original implementations: FontLab samples,
Apache-2.0; Scriptmix immutable provenance remains unchanged.
"""
from typing import Any

import PythonQt as qt

import fontlabapp.contours.affine as affine  # noqa: PLR0402 - native package lookup
import fontlabapp.contours.writer as outline_writer


def wrong_contours(contours: list[tuple[Any, Any]]) -> list[int]:
    """Use FontLab's start-and-midpoint nesting rule, in glyph coordinates.

    Each item is (contour, owning shape transform). All closed contours,
    including kept shapes, contribute to depth. Only callers choose edits.
    Native calculate(k + 0.5) evaluates the midpoint of segment k.
    """
    tests = [
        [
            transform.map(point)
            for k, segment in enumerate(contour.segments())
            for point in (segment.p0, contour.calculate(k + 0.5))
        ]
        for contour, transform in contours
    ]
    inverses = [affine.invert(affine.from_qtransform(tx)) for _, tx in contours]
    wrong = []
    for i, (contour, transform) in enumerate(contours):
        if not tests[i] or abs(float(contour.getSquare())) < 1e-9:
            continue
        depth = 0
        for j, (other, other_transform) in enumerate(contours):
            if i == j:
                continue
            inverse = inverses[j]
            if all(
                other.contains(
                    qt.QtCore.QPointF(*affine.apply(inverse, point.x(), point.y()))
                )
                for point in tests[i]
            ):
                depth += 1
        want_ccw = (depth % 2 == 0) != bool(contour.isTT)
        # Editable shapes only translate; kept mirrors still affect containment.
        if (not bool(contour.clockwise)) != want_ccw:
            wrong.append(i)
    return wrong


def direction_changes(layer: Any) -> list[outline_writer.Change]:
    """Use same-shape direction; keep cross-shape parity conflicts with a note."""
    shapes, notes = outline_writer.outline_shapes(layer)
    editable = {shape.id for shape in shapes}
    found = [
        (contour, shape)
        for shape in layer.shapes
        for contour in shape.contours
        if contour.closed
    ]
    layer_wrong = set(wrong_contours([(c, s.transform) for c, s in found]))
    shape_wrong = set()
    for shape in layer.shapes:
        indices = [i for i, (_, owner) in enumerate(found) if owner.id == shape.id]
        own = [(found[i][0], shape.transform) for i in indices]
        shape_wrong.update(indices[i] for i in wrong_contours(own))
    rows = []
    for index, (contour, shape) in enumerate(found):
        if shape.id not in editable:
            continue
        if (index in layer_wrong) != (index in shape_wrong):
            rows.append(
                outline_writer.Change(
                    f"contour {index + 1}", "", "inside another shape, direction left"
                )
            )
            continue
        if index not in shape_wrong:
            continue
        ccw = not bool(contour.clockwise)
        rows.append(
            outline_writer.Change(
                f"contour {index + 1}",
                "counter-clockwise" if ccw else "clockwise",
                "clockwise" if ccw else "counter-clockwise",
                (contour, not ccw),
            )
        )
    return rows + outline_writer.note_rows(notes)


def final_smooth_points(contours: list[Any]) -> set[tuple[float, float]]:
    """Coordinates of existing final off-curves with raw Smooth; read only."""
    result = set()
    for contour in contours:
        nodes = contour.nodes()
        if contour.closed and nodes and not nodes[-1].isOn() and nodes[-1].smooth:
            result.add((float(nodes[-1].x), float(nodes[-1].y)))
    return result


class ReverseEditor(outline_writer.Editor):
    """Reverse contours with FontLab's own flContour.reverse."""

    def __init__(self) -> None:
        self.before: dict[int, set[tuple[float, float]]] = {}
        self.advice: list[str] = []

    def prepare(self, layer: Any, edits: list[Any]) -> list[Any]:
        """Snapshot existing save-risk conditions before any history starts."""
        for edit in edits:
            contour = edit[0]
            self.before[id(contour)] = final_smooth_points([contour])
        return list(edits)

    def write(self, layer: Any, steps: list[Any]) -> None:
        for contour, _ in steps:
            contour.reverse()

    def check(self, prepared: list[tuple[Any, list[Any]]]) -> list[str]:
        missed: list[str] = []
        for layer, steps in prepared:
            for contour, ccw in steps:
                introduced = final_smooth_points([contour]) - self.before[id(contour)]
                if introduced:
                    message = (
                        f"{layer.name}: a final off-curve with raw Smooth was "
                        "introduced; FontLab may change on save (fl#8517). "
                        "Check node types after VFJ reopen."
                    )
                    if message not in self.advice:
                        self.advice.append(message)
                if (not bool(contour.clockwise)) != ccw:
                    missed.append(f"{layer.name}: a contour kept its direction")
        return missed


def bottom_left(points: list[outline_writer.Point]) -> int | None:
    """Index of the lowest, then leftmost on-curve point; None if there is
    none."""
    candidates = [(y, x, i) for i, (x, y, on) in enumerate(points) if on]
    return min(candidates)[2] if candidates else None


def own_contours(layer: Any) -> tuple[list[Any], list[str]]:
    """Contours of the editable shapes, in layer order, and notes for kept
    shapes.
    """
    shapes, notes = outline_writer.outline_shapes(layer)
    return [contour for shape in shapes for contour in shape.contours], notes


def start_changes(layer: Any, reference: Any | None) -> list[outline_writer.Change]:
    """One row per closed contour whose start moves; notes for kept shapes.

    With a `reference` layer, contour n uses the bottom-left node number of
    reference contour n when both have the same node count. Edit: (contour,
    new start index, position of that node).
    """
    contours, notes = own_contours(layer)
    sources = own_contours(reference)[0] if reference is not None else []
    rows = []
    for number, contour in enumerate(contours, start=1):
        if not contour.closed:
            continue
        points = outline_writer.node_points(contour)
        source = contour
        if (
            number <= len(sources)
            and sources[number - 1].nodesCount == contour.nodesCount
        ):
            source = sources[number - 1]
        index = bottom_left(outline_writer.node_points(source))
        if not index or not points[index][2]:
            continue
        x, y, _ = points[index]
        rows.append(
            outline_writer.Change(
                f"contour {number}",
                f"node 0 at {outline_writer.fmt(points[0][0])}, {outline_writer.fmt(points[0][1])}",
                f"node {index} at {outline_writer.fmt(x)}, {outline_writer.fmt(y)}",
                (contour, index, (x, y)),
                key=(number, index),
            )
        )
    return rows + outline_writer.note_rows(notes)


class StartEditor(outline_writer.Editor):
    """Rotate the node list with FontLab's own flContour.setStartPoint."""

    def __init__(self) -> None:
        self.before: dict[int, set[tuple[float, float]]] = {}
        self.advice: list[str] = []

    def prepare(self, layer: Any, edits: list[Any]) -> list[Any]:
        """Snapshot existing save-risk conditions before any history starts."""
        for edit in edits:
            contour = edit[0]
            self.before[id(contour)] = final_smooth_points([contour])
        return list(edits)

    def write(self, layer: Any, steps: list[Any]) -> None:
        for contour, index, _ in steps:
            if contour.setStartPoint(index) is False:
                raise RuntimeError(
                    f"FontLab refused start node {index} in {layer.name}."
                )

    def check(self, prepared: list[tuple[Any, list[Any]]]) -> list[str]:
        missed: list[str] = []
        for layer, steps in prepared:
            for contour, _, (x, y) in steps:
                introduced = final_smooth_points([contour]) - self.before[id(contour)]
                if introduced:
                    message = (
                        f"{layer.name}: a final off-curve with raw Smooth was "
                        "introduced; FontLab may change on save (fl#8517). "
                        "Check node types after VFJ reopen."
                    )
                    if message not in self.advice:
                        self.advice.append(message)
                first = outline_writer.node_points(contour)[0]
                if abs(first[0] - x) > 0.01 or abs(first[1] - y) > 0.01:
                    missed.append(
                        f"{layer.name}: start {outline_writer.fmt(first[0])}, {outline_writer.fmt(first[1])}"
                    )
        return missed
