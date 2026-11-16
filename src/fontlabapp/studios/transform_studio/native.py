# this_file: src/fontlabapp/studios/transform_studio/native.py
# SPDX-License-Identifier: Apache-2.0
"""Read one native FontLab layer into a ``geometry.Layer`` and write planned steps back.

What: ``snapshot(layer)`` copies shapes, contours, nodes (position, on-curve,
smooth, selection), anchors and the advance into plain tuples, retaining no
native wrapper. ``write(layer, steps)`` performs the steps inside the caller's
history scope: shape transforms through ``QTransform`` (baked with
``applyTransform`` for own outlines), node moves, node removal, anchor points
and the advance. ``shape.changed()`` follows every shape edit.
Why: the planners stay Qt-free; this is the only module that touches native
objects. Writes target the explicit layer a session resolved with
``flGlyph.findLayer``; never ``fgGlyph``.
"""

from typing import Any

from fontlabapp.core import sharing

from .geometry import IDENTITY, Affine, Contour, Layer, Node, Shape


def matrix_of(transform: Any) -> Affine:
    """Copy a QTransform into six floats; identity when there is none."""
    if transform is None:
        return IDENTITY
    return tuple(float(v) for v in (transform.m11(), transform.m12(), transform.m21(),
                                    transform.m22(), transform.dx(), transform.dy()))  # type: ignore[return-value]  # fmt: skip


def _contour_shared(shape: Any, layer: Any) -> bool:
    """Would moving this shape's points change another glyph? Component users do not count."""
    data = getattr(shape, "shapeData", None)
    return bool(data is not None and sharing.element_shared(shape, layer)) or bool(
        list(getattr(shape, "includesList", ()) or ())
    )


def _shared(shape: Any) -> bool:
    # Raw count on purpose: baking a transform rewrites the element data that
    # FontLab shares with component users, unlike a contour edit (core.sharing).
    data = getattr(shape, "shapeData", None)
    return bool(data is not None and int(data.referenceCount) > 1) or bool(
        list(getattr(shape, "includesList", ()) or ())
    )


def _box(shape: Any) -> tuple[float, float, float, float] | None:
    box = getattr(shape, "boundingBox", None)
    if box is None:
        return None
    return (
        float(box.x()),
        float(box.y()),
        float(box.x()) + float(box.width()),
        float(box.y()) + float(box.height()),
    )


def _contour(contour: Any) -> Contour:
    nodes = tuple(
        Node(float(n.x), float(n.y), bool(n.isOn()), bool(n.smooth), bool(n.selected))
        for n in contour.nodes()
    )
    return Contour(nodes, bool(contour.closed), bool(getattr(contour, "isTT", False)),
                   matrix_of(getattr(contour, "transform", None)))  # fmt: skip


@sharing.sharing_operation()  # one component-user count per layer read
def snapshot(layer: Any) -> Layer:
    """Plain copy of ``layer``; components keep their transform and local box."""
    shapes = []
    for shape in layer.shapes:
        component = bool(shape.isComponent)
        contours = () if component else tuple(_contour(c) for c in shape.contours)
        shapes.append(Shape(matrix_of(shape.transform), contours, component, bool(shape.contentLocked),
                            _contour_shared(shape, layer), bool(getattr(shape, "selected", False)),
                            _box(shape) if component else None, _shared(shape)))  # fmt: skip
    anchors = tuple(
        (str(pin.name), float(pin.point.x()), float(pin.point.y()))
        for pin in layer.anchors
    )
    body = not (
        bool(getattr(layer, "isMaskLayer", False))
        or bool(getattr(layer, "isService", False))
    )
    return Layer(
        tuple(shapes), anchors, float(layer.advanceWidth), bool(layer.isLocked), body
    )


def write(layer: Any, steps: tuple) -> None:
    """Perform ``steps`` on ``layer`` (inside the caller's history scope)."""
    from PythonQt import QtCore, QtGui

    shapes, pins = list(layer.shapes), list(layer.anchors)
    touched: dict[int, Any] = {}
    removals = []
    for step in steps:
        kind = step[0]
        if kind == "shape":
            _, s, matrix, bake = step
            shape = shapes[s]
            shape.transform = QtGui.QTransform(*matrix)
            if bake:
                shape.applyTransform()
            touched[s] = shape
        elif kind == "node":
            _, s, c, i, x, y, smooth = step
            node = list(shapes[s].contours)[c].nodes()[i]
            node.x, node.y = float(x), float(y)
            if smooth is not None:
                node.smooth = bool(smooth)
            touched[s] = shapes[s]
        elif kind == "remove":
            removals.append(step)
        elif kind == "anchor":
            pins[step[1]].point = QtCore.QPointF(float(step[2]), float(step[3]))
        else:
            layer.advanceWidth = float(step[1])
    for _, s, c, indices, _count in removals:
        contour = list(shapes[s].contours)[c]
        for index in sorted(indices, reverse=True):
            contour.removeAt(index)
        touched[s] = shapes[s]
    for shape in touched.values():
        shape.changed()
