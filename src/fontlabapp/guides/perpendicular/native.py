# this_file: src/fontlabapp/guides/perpendicular/native.py
# SPDX-License-Identifier: Apache-2.0
"""Bound first-layer guide writer; never clone outlines or refresh the whole font.

Native selected-layer ownership, component cache reads and complete font
Apply/Undo/Redo/save/reopen preservation still require owned-host qualification.
Existing guides, shapes, nodes, notes and metadata are retained in place.
"""

from dataclasses import dataclass, field
from importlib import import_module
from math import degrees
from time import monotonic
from typing import Any

import fontlabapp.core.edit_guards as edit_guards
from fontlabapp import _native
from fontlabapp.contours.angularizzle._native_records import matrix as transform_record
from fontlabapp.anchors.duplicates.capture import check, require_main_thread
from fontlabapp.guides.inspect.model import (
    affected_auto_layers,
    dependency_values,
    new_guide,
)
from fontlabapp.guides.perpendicular.model import TITLE, plan
from fontlabapp.core.history.glyphs import PartialWriteError, UNDO_HINT

# Package __getattr__ forwards unknown names to FontLab; use explicit submodule import.
layer_selection = import_module("fontlabapp.guides.perpendicular.selection")


@dataclass(frozen=True)
class Snapshot:
    """Scalar source witnesses and retained exact native target owners."""

    facts: tuple
    nodes: tuple
    components: tuple
    dependencies: tuple
    occurrence: Any = field(compare=False, repr=False)
    carriers: tuple = field(default=(), compare=False, repr=False)


def capture(deadline: float) -> Snapshot:
    """Capture ordered own nodes in layer space and transformed component bounds.

    getCompositesBounding uses native _getInkBox, including component transforms;
    a mapped local bounding rectangle would be wrong for rotated curved outlines.
    Native component builder cache side effects remain a qualification boundary.
    """
    selection = layer_selection.capture(deadline)
    if not selection.occurrences:
        raise ValueError("Select a glyph layer before adding guides.")
    occurrence = selection.occurrences[0]
    layer = occurrence.layer
    nodes, components, shapes = [], [], []
    for shape in layer.shapes:
        check(deadline)
        matrix = shape.transform
        if not matrix.isAffine():
            raise ValueError("Selected-layer guide geometry requires affine shapes.")
        points, contours = [], []
        if shape.isComponent:
            if shape.selected:
                bounds = shape.getCompositesBounding()
                components.append(
                    (
                        int(shape.id),
                        bounds.x(),
                        bounds.y(),
                        bounds.width(),
                        bounds.height(),
                    )
                )
        else:
            for contour in shape.contours:
                contour_transform = contour.transform
                if not contour_transform.isAffine():
                    raise ValueError(
                        "Selected-layer guide geometry requires affine contours."
                    )
                contours.append(
                    (
                        int(contour.id),
                        transform_record(contour_transform, editable=False),
                    )
                )
                for node in contour.nodes():
                    check(deadline)
                    point = matrix.map(contour_transform.map(node.position))
                    row = (int(node.id), float(point.x()), float(point.y()))
                    points.append((*row, int(node.nodeState), bool(node.selected)))
                    if node.selected:
                        nodes.append(row)
        shapes.append(
            (
                int(shape.id),
                bool(shape.selected),
                transform_record(matrix, editable=False),
                tuple(contours),
                tuple(points),
            )
        )
    dependencies = dependency_values(occurrence.package)
    facts = (
        selection.context,
        tuple(
            (o.package_id, o.glyph_id, o.layer_id, o.block_id, o.index)
            for o in selection.occurrences
        ),
        bool(layer.autoLayer),
        tuple(shapes),
        tuple(int(g.id) for g in layer.guidelines),
    )
    check(deadline)
    return Snapshot(
        facts,
        tuple(nodes),
        tuple(components),
        dependencies,
        occurrence,
        selection.carriers,
    )


def write(source: Snapshot, guides: tuple, deadline: float) -> dict:
    """Construct every guide before history; finalize attempted append once.

    Partial errors are reported, never disguised as successful rollback. No
    UpdateAll, global update-queue clearing, outline clone or selection writer.
    """
    if not guides:
        return {"guides": 0, "layers": 0, "pending_updates": (), "pending_note": ""}
    target = source.occurrence
    if target.layer.autoLayer or affected_auto_layers(
        source.dependencies, {target.glyph.name}
    ):
        raise ValueError(
            "Cannot safely undo guide edits to automatic layers or their dependants."
        )
    prepared = tuple(new_guide((x, y, degrees(angle), "")) for x, y, angle in guides)
    if capture(deadline) != source:
        raise ValueError("Source changed before guide history; run again.")
    native = _native("fontlab")
    edit_guards.require_history_scope((target.glyph,), native=native)
    ids = edit_guards.pending_updates(native)
    pending = {"pending_updates": ids, "pending_note": edit_guards.pending_note(ids)}
    edit_guards.disclose(pending)
    objects = [target.layer, target.glyph]
    for obj in objects:
        check(deadline)
        obj.checkInitHistoryState(0)
    stamp = _native("PythonQt").QtCore.QDateTime.currentDateTimeUtc()
    check(deadline)
    errors = []
    try:
        target.layer.appendGuidelines(list(prepared))
        if tuple(int(g.id) for g in target.layer.guidelines) != source.facts[
            -1
        ] + tuple(int(g.id) for g in prepared):
            raise RuntimeError(
                "Native guide append did not preserve the complete ordered guide list."
            )
    except BaseException as error:  # noqa: BLE001 - retain the append failure and finalize
        errors.append(error)
    finally:
        try:
            target.glyph.lastModified = stamp
        except BaseException as error:  # noqa: BLE001 - a stamp failure must not skip notification
            errors.append(error)
        try:
            native.flItems().notifyChangesApplied(TITLE, objects)
        except BaseException as error:  # noqa: BLE001 - keep notification and append failures
            errors.append(error)
        try:
            target.glyph.lastModified = stamp
        except BaseException as error:  # noqa: BLE001 - retain final stamp failure too
            errors.append(error)
    for error in errors:
        if not isinstance(error, Exception):
            for other in errors:
                if other is not error:
                    error.add_note(f"{TITLE}: {type(other).__name__}: {other}")
            error.add_note(UNDO_HINT)
            raise error
    if errors:
        raise PartialWriteError(TITLE, errors) from errors[0]
    return {"guides": len(prepared), "layers": 1, **pending}


def execute() -> dict:
    """Read twice, plan every original branch, then write only the first layer."""
    require_main_thread()
    deadline = monotonic() + 2
    first = capture(deadline)
    if capture(deadline) != first:
        raise ValueError("Selection or geometry changed during guide capture.")
    rows, messages = plan(first.nodes, first.components)
    result = write(first, rows, deadline)
    for message in messages:
        print(message)
    if len(first.nodes) >= 2:
        x, y, angle = rows[0]
        print(f"Added perpendicular guide at ({x}, {y}) with angle {degrees(angle)}°.")
    for _, x, y, width, height in first.components:
        print(
            f"Added horizontal and vertical guides at center ({x + width / 2}, {y + height / 2}) for component."
        )
    return {**result, "messages": messages}
