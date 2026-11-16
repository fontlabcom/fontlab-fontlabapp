# this_file: src/fontlabapp/contours/angularizzle/_native_records.py
# SPDX-License-Identifier: Apache-2.0
"""Read explicit bound native fields; never introspect arbitrary Qt properties.

Contour.segments/CurveEx sequences and transform.map follow official pyflcontour,
pycurveex and pyflshape bindings. Keep raw local nodes beside layer-space inputs.
"""

from math import isfinite
from typing import Any

from fontlabapp.contours.angularizzle.model import Path, Segment, _check_deadline

MATRIX = ("m11", "m12", "m13", "m21", "m22", "m23", "m31", "m32", "m33")


def number(value: Any) -> float:
    value = float(value)
    if not isfinite(value):
        raise ValueError("Angularizzle source contains nonfinite coordinates.")
    return value


def matrix(transform: Any, *, editable: bool = True) -> tuple:
    if editable and (not transform.isAffine() or not transform.isInvertible()):
        raise ValueError(
            "Angularizzle needs finite invertible affine shape transforms."
        )
    return tuple(number(getattr(transform, key)()) for key in MATRIX)


def frozen(value: Any, deadline: float) -> Any:
    """Copy native lib's explicit scalar containers, refusing opaque mutable data."""
    _check_deadline(deadline)
    if isinstance(value, dict):
        return tuple(sorted((str(k), frozen(v, deadline)) for k, v in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(frozen(v, deadline) for v in value)
    if isinstance(value, float):
        return number(value)
    if value is None or isinstance(value, (str, bool, int, bytes)):
        return value
    raise ValueError("Angularizzle cannot checkpoint an opaque layer lib value.")


def shape_record(shape: Any, deadline: float) -> tuple:
    data = shape.shapeData
    contours = []
    for contour in shape.contours:
        _check_deadline(deadline)
        nodes = []
        for node in contour.nodes():
            _check_deadline(deadline)
            nodes.append(
                (
                    int(node.id),
                    number(node.position.x()),
                    number(node.position.y()),
                    int(node.nodeState),
                    str(node.name),
                )
            )
        contours.append(
            (int(contour.id), bool(contour.closed), bool(contour.isTT), tuple(nodes))
        )
    component = (
        (str(data.componentGlyph), str(data.componentLayer))
        if shape.isComponent
        else ()
    )
    return (
        int(shape.id),
        int(data.id),
        bool(shape.isComponent),
        bool(shape.isComposite),
        matrix(
            shape.transform, editable=not shape.isComponent and bool(shape.contours)
        ),
        bool(shape.active),
        bool(shape.selected),
        number(shape.opacity),
        bool(shape.excluded),
        bool(shape.contentLocked),
        shape.pen,
        shape.brush,
        str(data.name),
        str(data.note),
        component,
        tuple(contours),
    )


def read_layer(layer: Any, deadline: float) -> tuple[tuple[Path, ...], tuple, tuple]:
    """Read complete own-path order and fixed metadata; refuse unsupported writers."""
    _check_deadline(deadline)
    if layer.autoLayer:
        raise ValueError("Angularizzle cannot safely edit automatic layers.")
    if layer.tthProgram or layer.ttData.hasHints():
        raise ValueError("Angularizzle cannot safely replace TrueType hinted paths.")
    guides = []
    for guide in layer.guidelines:
        _check_deadline(deadline)
        if guide.isHint:
            raise ValueError(
                "Angularizzle cannot safely replace PostScript hinted paths."
            )
        guides.append(int(guide.id))
    paths, owners, shapes = [], [], []
    for index, shape in enumerate(layer.shapes):
        _check_deadline(deadline)
        if shape.isComposite and not shape.isComponent:
            raise ValueError("Angularizzle cannot replace nested composite contours.")
        if not shape.isComponent:
            builder = shape.shapeData.builder
            if builder is not None and not builder.isNull:
                raise ValueError(
                    "Angularizzle cannot replace a generated shape builder."
                )
            for contour in shape.contours:
                _check_deadline(deadline)
                if contour.isTT:
                    raise ValueError(
                        "Angularizzle does not support quadratic contours."
                    )
                segments = []
                for curve in contour.segments():
                    _check_deadline(deadline)
                    points = []
                    for point in curve:
                        _check_deadline(deadline)
                        mapped = shape.transform.map(point)
                        points.append((number(mapped.x()), number(mapped.y())))
                    if len(points) not in (2, 4):
                        raise ValueError(
                            "Angularizzle expects line or cubic source segments."
                        )
                    segments.append(Segment(tuple(points)))
                paths.append(Path(tuple(segments), bool(contour.closed)))
                owners.append(index)
        shapes.append(shape_record(shape, deadline))
    metadata = (
        str(layer.name),
        int(layer.mark),
        str(layer.note),
        str(layer.recipe),
        number(layer.advanceWidth),
        number(layer.advanceHeight),
        str(layer.metricsLeft),
        str(layer.metricsRight),
        str(layer.metricsWidth),
        matrix(layer.transform, editable=False),
        frozen(layer.lib, deadline),
        tuple(guides),
        tuple(int(a.id) for a in layer.anchors),
        tuple(shapes),
    )
    _check_deadline(deadline)
    return tuple(paths), metadata, tuple(owners)


def clone_shape(shape: Any, deadline: float) -> Any:
    """Copy detached geometry; undo native clone's checkSmooth and old note loss."""
    _check_deadline(deadline)
    clone = shape.clone()
    if (
        clone is None
        or int(clone.id) == int(shape.id)
        or int(clone.shapeData.id) == int(shape.shapeData.id)
    ):
        raise ValueError("Angularizzle native clone did not detach its ShapeData.")
    clone.shapeData.note, clone.shapeData.name = (
        shape.shapeData.note,
        shape.shapeData.name,
    )
    clone.active, clone.selected = shape.active, shape.selected
    for field in ("opacity", "excluded", "contentLocked", "pen", "brush"):
        if getattr(shape, field) != getattr(clone, field):
            raise ValueError("Angularizzle native clone changed retained shape style.")
    if matrix(shape.transform) != matrix(clone.transform):
        raise ValueError("Angularizzle native clone changed the shape transform.")
    for old, new in zip(shape.contours, clone.contours, strict=True):
        if (bool(old.closed), bool(old.isTT)) != (bool(new.closed), bool(new.isTT)):
            raise ValueError("Angularizzle native clone changed contour topology.")
        for source, target in zip(old.nodes(), new.nodes(), strict=True):
            _check_deadline(deadline)
            if (source.position.x(), source.position.y()) != (
                target.position.x(),
                target.position.y(),
            ):
                raise ValueError("Angularizzle native clone changed node geometry.")
            target.nodeState = source.nodeState
            target.name = source.name
    _check_deadline(deadline)
    return clone
