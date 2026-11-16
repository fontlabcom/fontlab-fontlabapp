# this_file: src/fontlabapp/masters/background/stage.py
# SPDX-License-Identifier: Apache-2.0
"""Stage complete detached geometry before any font history or mutation."""

from typing import Any

from fontlabapp.masters.background.records import check, clone, matrix
from fontlabapp.masters.background.model import Transform, selected_paths


def transform_shape(
    source: Any, operation: Transform, repeat: int, qt: Any, deadline: float
) -> Any:
    """Transform own nodes in layer coordinates; Scale leaves components attached."""
    if source.isComponent and operation.mode == "scale":
        return source
    if not source.isComponent and not source.contours:
        return source
    result = clone(source, deadline)
    if source.isComponent:
        values = matrix(source.transform, editable=False)
        for _ in range(repeat):
            values = operation.component(values)
        result.transform = qt.QtGui.QTransform(*values)
        if matrix(result.transform, editable=False) != values:
            raise ValueError("Background component transform did not stick.")
        return result
    inverse = source.transform.inverted()
    for contour in result.contours:
        for node in contour.nodes():
            check(deadline)
            state = int(node.nodeState)
            world = source.transform.map(node.position)
            point = operation.points(((world.x(), world.y()),), repeat=repeat)[0]
            local = inverse.map(qt.QtCore.QPointF(*point))
            node.position = local
            node.nodeState = state
            actual = source.transform.map(node.position)
            if abs(actual.x() - point[0]) > 1e-8 or abs(actual.y() - point[1]) > 1e-8:
                raise ValueError("Background node position did not stick.")
    return result


def selected_shapes(layer: Any, native: Any, qt: Any, deadline: float) -> tuple:
    """Reconstruct only selected own contours, preserving every native node bit.

    Full node sequences retain cubic/quadratic topology; no polygon sampling.
    No unselected path geometry or component reference is read or cloned.
    """
    result = []
    for shape in layer.shapes:
        check(deadline)
        if shape.isComponent:
            continue
        contours = tuple(shape.contours)
        indices = selected_paths(
            tuple(tuple(bool(n.selected) for n in c.nodes()) for c in contours)
        )
        if not indices:
            continue
        copy = native.flShape()
        copy.assignStyle(shape)
        copy.transform = shape.transform
        copy.shapeData.name, copy.shapeData.note = (
            shape.shapeData.name,
            shape.shapeData.note,
        )
        copy.active, copy.selected = shape.active, False
        for index in indices:
            source = contours[index]
            nodes = []
            for old in source.nodes():
                check(deadline)
                node = native.flNode(
                    qt.QtCore.QPointF(old.position.x(), old.position.y()), nodeType="on"
                )
                node.nodeState = int(old.nodeState) & ~0x20
                node.name = str(old.name)
                nodes.append(node)
            expected = tuple(
                (n.position.x(), n.position.y(), n.nodeState, n.name) for n in nodes
            )
            contour = native.flContour(nodes, closed=bool(source.closed))
            contour.closed = bool(source.closed)
            if bool(contour.isTT) != bool(source.isTT):
                raise ValueError("Background copy changed quadratic/cubic topology.")
            copy.addContour(contour, False, False)
            actual = tuple(
                (n.position.x(), n.position.y(), n.nodeState, n.name)
                for n in contour.nodes()
            )
            if actual != expected or bool(contour.closed) != bool(source.closed):
                raise ValueError("Background copy changed the complete node sequence.")
        if len(copy.contours) != len(indices):
            raise ValueError("Background copy rejected a selected contour.")
        result.append(copy)
    return tuple(result)
