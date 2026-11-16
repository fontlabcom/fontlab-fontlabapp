# this_file: src/fontlabapp/masters/background/records.py
# SPDX-License-Identifier: Apache-2.0
"""Explicit background fingerprints and shared rich detached-copy controls."""

from typing import Any

from fontlabapp.contours.angularizzle._native_records import (
    clone_shape,
    frozen,
    matrix,
    shape_record,
)
from fontlabapp.contours.angularizzle.model import _check_deadline as check
from fontlabapp.masters.background.model import selected_paths


def layer_record(
    layer: Any, deadline: float, *, components: bool = True
) -> tuple | None:
    """Read only this mask's own content, metadata and retained object identities."""
    if layer is None:
        return None
    check(deadline)
    return (
        int(layer.id),
        str(layer.name),
        str(layer.note),
        str(layer.recipe),
        frozen(layer.lib, deadline),
        float(layer.advanceWidth),
        float(layer.advanceHeight),
        str(layer.metricsLeft),
        str(layer.metricsRight),
        str(layer.metricsWidth),
        matrix(layer.transform, editable=False),
        bool(layer.isLocked),
        bool(layer.isVisible),
        bool(layer.isService),
        bool(layer.isWireframe),
        tuple(
            shape_record(s, deadline)
            if components or not s.isComponent
            else (int(s.id), "untouched component")
            for s in layer.shapes
        ),
        tuple(int(a.id) for a in layer.anchors),
        tuple(int(g.id) for g in layer.guidelines),
    )


def clone(shape: Any, deadline: float) -> Any:
    """Reuse path clone calibration; preserve component refs and raw style too."""
    if not shape.isComponent:
        return clone_shape(shape, deadline)
    check(deadline)
    result = shape.clone()
    if (
        result is None
        or int(result.id) == int(shape.id)
        or int(result.shapeData.id) == int(shape.shapeData.id)
    ):
        raise ValueError("Background component clone did not detach.")
    result.shapeData.note, result.shapeData.name = (
        shape.shapeData.note,
        shape.shapeData.name,
    )
    result.active, result.selected = shape.active, shape.selected
    for key in ("opacity", "excluded", "contentLocked", "pen", "brush"):
        if getattr(result, key) != getattr(shape, key):
            raise ValueError("Background component clone changed retained style.")
    if matrix(result.transform, editable=False) != matrix(
        shape.transform, editable=False
    ) or (result.shapeData.componentGlyph, result.shapeData.componentLayer) != (
        shape.shapeData.componentGlyph,
        shape.shapeData.componentLayer,
    ):
        raise ValueError(
            "Background component clone changed its reference or transform."
        )
    check(deadline)
    return result


def selection_record(layer: Any, deadline: float) -> tuple:
    """Read selection for every own path, geometry only for selected paths."""
    rows = []
    for shape in layer.shapes:
        check(deadline)
        if shape.isComponent:
            continue
        contours = tuple(shape.contours)
        flags = tuple(tuple(bool(n.selected) for n in c.nodes()) for c in contours)
        indices = selected_paths(flags)
        geometry = tuple(
            (
                int(contours[i].id),
                bool(contours[i].closed),
                bool(contours[i].isTT),
                tuple(
                    (
                        int(n.id),
                        float(n.position.x()),
                        float(n.position.y()),
                        int(n.nodeState),
                        str(n.name),
                    )
                    for n in contours[i].nodes()
                ),
            )
            for i in indices
        )
        style = (
            (
                matrix(shape.transform, editable=False),
                str(shape.shapeData.note),
                str(shape.shapeData.name),
                bool(shape.active),
                bool(shape.contentLocked),
                shape.pen,
                shape.brush,
                float(shape.opacity),
                bool(shape.excluded),
            )
            if indices
            else ()
        )
        rows.append((int(shape.id), flags, geometry, style))
    return tuple(rows)
