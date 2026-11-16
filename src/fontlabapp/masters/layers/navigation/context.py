# this_file: src/fontlabapp/masters/layers/navigation/context.py
# SPDX-License-Identifier: Apache-2.0
"""Exact native layer families and bounded viewport/activation restoration."""

from typing import Any


def _layers(package: Any, glyph: Any, active_name: str) -> tuple:
    masters = tuple(package.masters)
    if not masters or len(set(masters)) != len(masters):
        raise ValueError("Missing or ambiguous font masters")
    layers = tuple(
        layer for layer in glyph.layers if not layer.isService and not layer.isMaskLayer
    )
    names = tuple(layer.name for layer in layers)
    if not names or any(not name for name in names) or len(set(names)) != len(names):
        raise ValueError("Empty or ambiguous native layer names")
    all_names = tuple(layer.name for layer in glyph.layers)
    if any(all_names.count(name) != 1 for name in names):
        raise ValueError("Eligible layer name collides with another native layer")
    if active_name not in names:
        raise ValueError("Current layer has no exact eligible mapping")
    associations = {}
    for name in names:
        root = name if name in masters else name.partition(".")[0]
        if root not in masters:
            if len(masters) != 1:
                raise ValueError("Unassociated auxiliary in a multi-master font")
            root = masters[0]
        if root not in names:
            raise ValueError("Associated master layer is absent from this glyph")
        associations[name] = root
    return tuple(
        layer
        for layer in layers
        if associations[layer.name] == associations[active_name]
    )


def _context(canvas: Any, glyph: Any) -> tuple:
    point, transform = canvas.viewPoint, canvas.viewTransform.transform
    matrix = tuple(
        getattr(transform, f"m{row}{column}")()
        for row in range(1, 4)
        for column in range(1, 4)
    )
    shapes = tuple(
        (shape.id, bool(shape.active))
        for layer in glyph.layers
        for shape in layer.shapes
    )
    return (point.x(), point.y(), matrix, glyph.activeLayer.id, shapes)


def _restore(assignments: list[tuple[Any, str, Any]]) -> None:
    errors = []
    for owner, field, value in assignments:
        try:
            if field == "active" and owner.active == value:
                continue
            if field == "activeLayer" and owner.activeLayer.id == value.id:
                continue
            setattr(owner, field, value)
        except Exception as error:  # noqa: BLE001 - attempt every native restoration.
            errors.append(str(error))
    if errors:
        raise RuntimeError("Context restoration failed: " + "; ".join(errors))
