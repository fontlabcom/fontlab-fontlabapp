# this_file: src/fontlabapp/contours/raise_ascender/_geometry.py
# SPDX-License-Identifier: MIT AND Apache-2.0
"""Capture original own nodes and stage detached coordinate-only shape copies."""

from typing import Any

from fontlabapp.contours.angularizzle._native_records import clone_shape, frozen, matrix
from fontlabapp.contours.raise_ascender.model import Point, Step, check, number


def read(layer: Any, deadline: float, shapes: tuple | None = None) -> tuple:
    """Include quadratic controls; components remain original objects, never expanded."""
    check(deadline)
    points, facts, handles = [], [], []
    for index, shape in enumerate(layer.shapes if shapes is None else shapes):
        check(deadline)
        data = shape.shapeData
        if shape.isComponent:
            facts.append(
                (
                    int(shape.id),
                    "component",
                    str(data.componentGlyph),
                    str(data.componentLayer),
                    matrix(shape.transform, editable=False),
                )
            )
            continue
        if shape.isComposite or (data.builder is not None and not data.builder.isNull):
            raise ValueError(
                "Generated or nested own geometry requires native qualification; no layer is omitted."
            )
        transform = shape.transform
        transform_values = matrix(transform)
        contours = []
        for contour in shape.contours:
            check(deadline)
            nodes = []
            for node in contour.nodes():
                check(deadline)
                local = node.position
                mapped = transform.map(local)
                points.append(Point(number(mapped.x()), number(mapped.y())))
                nodes.append(
                    (
                        int(node.id),
                        number(local.x()),
                        number(local.y()),
                        int(node.nodeState),
                        str(node.name),
                    )
                )
                handles.append((index, int(contour.id), int(node.id)))
            contours.append(
                (
                    int(contour.id),
                    bool(contour.closed),
                    bool(contour.isTT),
                    tuple(nodes),
                )
            )
        facts.append(
            (
                int(shape.id),
                int(data.id),
                transform_values,
                str(data.name),
                str(data.note),
                bool(shape.active),
                bool(shape.selected),
                shape.pen,
                shape.brush,
                number(shape.opacity),
                bool(shape.excluded),
                bool(shape.contentLocked),
                tuple(contours),
            )
        )
    metadata = (
        str(layer.name),
        str(layer.note),
        str(layer.recipe),
        int(layer.mark),
        number(layer.advanceWidth),
        number(layer.advanceHeight),
        str(layer.metricsLeft),
        str(layer.metricsRight),
        str(layer.metricsWidth),
        frozen(layer.lib, deadline),
        tuple(int(pin.id) for pin in layer.anchors),
        tuple(int(guide.id) for guide in layer.guidelines),
        tuple(facts),
    )
    check(deadline)
    return tuple(points), metadata, tuple(handles)


def prepare(layer: Any, step: Step, shapes: tuple, qt: Any, deadline: float) -> tuple:
    """Detach changed owners only; preserve exact topology, flags, hints and styles.

    Native hinted-node reference remapping and history are still unqualified.
    Refuse hinted layers instead of replacing them with unlinked hint payloads.
    """
    check(deadline)
    if not step.changed:
        return (), shapes
    if layer.isLocked or layer.autoLayer or layer.tthProgram or layer.ttData.hasHints():
        raise ValueError(
            "Locked, automatic or TrueType-hinted layer changes remain unsupported; no partial action."
        )
    if any(guide.isHint for guide in layer.guidelines):
        raise ValueError(
            "PostScript-hinted layer changes require native hint-link qualification."
        )
    updated, jobs, offset = list(shapes), [], 0
    for index, shape in enumerate(shapes):
        check(deadline)
        if shape.isComponent:
            continue
        count = 0
        for contour in shape.contours:
            check(deadline)
            for _ in contour.nodes():
                check(deadline)
                count += 1
        before, after = (
            step.before[offset : offset + count],
            step.after[offset : offset + count],
        )
        offset += count
        if before == after:
            continue
        clone = clone_shape(shape, deadline)
        inverse = clone.transform.inverted()
        # PySide exposes the bool* output as a tuple; PythonQt returns QTransform.
        if isinstance(inverse, tuple):
            inverse, invertible = inverse
            if not invertible:
                raise ValueError("A staged transform became singular.")
        expected = iter(after)
        for contour in clone.contours:
            check(deadline)
            for node in contour.nodes():
                check(deadline)
                point = next(expected)
                local = inverse.map(qt.QtCore.QPointF(point.x, point.y))
                flags, name = node.nodeState, node.name
                node.position = (number(local.x()), number(local.y()))
                node.nodeState, node.name = flags, name
                actual = clone.transform.map(node.position)
                if (actual.x(), actual.y()) != (point.x, point.y):
                    raise ValueError(
                        "Native coordinate setter cannot represent the exact requested point."
                    )
        updated[index] = clone
        jobs.append((index, shape, clone))
    if offset != len(step.after):
        raise ValueError("Own node domain changed while staging.")
    check(deadline)
    return tuple(jobs), tuple(updated)
