# this_file: src/fontlabapp/contours/selection/native.py
# SPDX-License-Identifier: Apache-2.0
"""Lazy native transport for Pedro Arilla's three contour selection algorithms.

Only selection setters are used. No history, notifications or geometry writers.
Mixed visual selection in a multi-glyph canvas is refused because PythonQt's
generic flVisualItem binding does not expose the owning model layer.
"""

from dataclasses import dataclass, field
from time import monotonic
from typing import Any

import fontlabapp.masters.layers.selection as layer_selection
from fontlabapp.contours.angularizzle._native_records import matrix
from fontlabapp.contours.selection.model import (
    Mode,
    Path,
    Plan,
    plan,
    threshold,
    unsigned_area,
)
from fontlabapp.contours.nodes.coordinates import own_contours

# Proteus/common/model/flnode.h and flmodel.h, source-reviewed with this adapter.
SELECTED = 0x0020
SHAPE_ITEM, PIN_POINT_ITEM = 1022, 1043


@dataclass(frozen=True)
class Snapshot:
    """Immutable source facts with retained handles excluded from equality."""

    context: Any
    geometry: tuple
    paths: tuple[Path, ...]
    other: tuple
    smart: tuple
    nodes: tuple = field(compare=False, repr=False)
    items: tuple = field(compare=False, repr=False)


def _check(deadline: float) -> None:
    if monotonic() >= deadline:
        raise TimeoutError("Contour selection exceeded its deadline before completion.")


def _visual_items(selected: Any, deadline: float, clearing: bool) -> tuple:
    """Capture selected canvas items; never guess ownership across glyph slots.

    Shapes are also captured from the layer, including selected components.
    Anchor model selection has no Python binding; its actual visual flag is used.
    Single-slot canvas scope and item types still require native qualification.
    """
    if selected.context[2] != "editor":
        return ()
    canvas = selected.carriers[0]
    items = tuple(canvas.selection())
    if clearing and items and sum(int(b.glyphsCount()) for b in canvas.textBlocks) != 1:
        raise ValueError(
            "Mixed selection in a multi-glyph canvas needs native ownership support; select one displayed glyph."
        )
    for item in items:
        _check(deadline)
        if clearing and int(item.type) not in (SHAPE_ITEM, PIN_POINT_ITEM):
            raise ValueError(
                "This selected native item cannot safely be cleared in the current layer."
            )
    return items


def capture(*, area: bool = False) -> Snapshot:
    """Read first selected layer only, preserving own shape/node order and types."""
    deadline = monotonic() + 2
    if area:
        unsigned_area(())  # Verify the optional dependency before any clearing.
    selected = layer_selection.capture(deadline)
    if not selected.occurrences:
        raise ValueError("Select a glyph layer before selecting contours.")
    occurrence = selected.occurrences[0]
    layer = occurrence.layer
    if area and selected.context[2] != "editor" and (layer.anchors or layer.guidelines):
        raise ValueError(
            "Open this glyph in a Glyph window to capture its anchor and guide selection safely."
        )
    nodes, paths, geometry, smart = [], [], [], []
    for shape in layer.shapes:
        _check(deadline)
        geometry.append(
            (
                int(shape.id),
                bool(shape.isComponent),
                matrix(shape.transform, editable=False),
            )
        )
    for contour in own_contours(layer):
        _check(deadline)
        row = tuple(contour.nodes())
        state = tuple(
            (int(n.id), float(n.x), float(n.y), int(n.nodeState) & ~SELECTED)
            for n in row
        )
        geometry.append(
            (int(contour.id), bool(contour.closed), bool(contour.isTT), state)
        )
        nodes.append(row)
        smart.append(tuple(n.getProperty("__smart_selected") for n in row))
        measured = None
        if area:
            # Native CurveEx segments retain quadratic/cubic topology. Use the
            # owning shape's mapping, as in existing Angularizzle extraction.
            shape = next(
                s
                for s in layer.shapes
                if any(int(c.id) == int(contour.id) for c in s.contours)
            )
            if not shape.transform.isAffine():
                raise ValueError(
                    "Small-contour area requires an affine shape transform."
                )
            segments = tuple(
                tuple(
                    (float(p.x()), float(p.y()))
                    for p in (shape.transform.map(p) for p in curve)
                )
                for curve in contour.segments()
            )
            measured = unsigned_area(segments)
        paths.append(Path(tuple(bool(n.selected) for n in row), measured))
    shapes = tuple(layer.shapes)
    visual = _visual_items(selected, deadline, area)
    items = (*shapes, *visual)
    other = tuple((int(i.id), bool(i.selected)) for i in items)
    _check(deadline)
    context = (
        selected.context,
        tuple(
            (o.package_id, o.glyph_id, o.layer_id, o.block_id, o.index)
            for o in selected.occurrences
        ),
    )
    return Snapshot(
        context,
        (matrix(layer.transform, editable=False), tuple(geometry)),
        tuple(paths),
        other,
        tuple(smart),
        tuple(nodes),
        items,
    )


def apply(source: Snapshot, target: Plan) -> int:
    """Recheck before writes; restore attempted selection flags after late errors."""
    if capture(area=target.clear_other) != source:
        raise ValueError(
            "Font, glyph, layer, master, geometry or selection changed; reopen the tool."
        )
    if tuple(map(len, target.nodes)) != tuple(map(len, source.nodes)):
        raise ValueError("Selection plan does not match the captured contour topology.")
    writes = []
    if target.clear_other:
        writes.extend(
            (item, old, False, None)
            for item, (_, old) in zip(source.items, source.other)
            if old
        )
    for row, old, new, smart in zip(
        source.nodes, source.paths, target.nodes, source.smart
    ):
        writes.extend(
            (node, previous, wanted, flag)
            for node, previous, wanted, flag in zip(row, old.selected, new, smart)
            if previous != wanted
        )
    try:
        for item, old, wanted, smart in writes:
            item.selected = wanted
            if bool(item.selected) != wanted:
                raise RuntimeError(
                    "A native selection setter did not retain its target."
                )
        actual = capture(area=target.clear_other)
        if (
            actual.context != source.context
            or actual.geometry != source.geometry
            or tuple(p.selected for p in actual.paths) != target.nodes
        ):
            raise RuntimeError(
                "Native selection verification found an unexpected delta."
            )
        if target.clear_other and any(flag for _, flag in actual.other):
            raise RuntimeError("A non-node selection was not cleared.")
        if not target.clear_other and actual.other != source.other:
            raise RuntimeError("A non-node selection changed unexpectedly.")
        expected_smart = tuple(
            tuple(
                False if old and not wanted else flag
                for old, wanted, flag in zip(path.selected, wanted_row, flags)
            )
            for path, wanted_row, flags in zip(source.paths, target.nodes, source.smart)
        )
        if actual.smart != expected_smart:
            raise RuntimeError("Native smart-selection flags changed unexpectedly.")
    except Exception as error:
        failures = []
        originals = [
            (item, old, None) for item, (_, old) in zip(source.items, source.other)
        ]
        originals.extend(
            (node, old, smart)
            for row, path, flags in zip(source.nodes, source.paths, source.smart)
            for node, old, smart in zip(row, path.selected, flags)
        )
        for item, old, smart in reversed(originals):
            try:
                if bool(item.selected) != old:
                    item.selected = old
                if smart is not None and item.getProperty("__smart_selected") != smart:
                    item.setProperty("__smart_selected", smart)
                if bool(item.selected) != old:
                    raise RuntimeError("restored flag differs")
            except Exception as restore:
                failures.append(str(restore))
        try:
            if capture(area=target.clear_other) != source:
                failures.append(
                    "restored complete selection differs from opening state"
                )
        except Exception as restore:
            failures.append(f"restoration verification: {restore}")
        raise RuntimeError(
            f"Selection may be partial: {error}; restoration {'failed: ' + '; '.join(failures) if failures else 'completed for captured flags'}"
        ) from error
    return target.paths


def execute(mode: Mode, value: Any = None, *, source: Snapshot | None = None) -> int:
    """Run a public action against fresh context or a dialog's opening snapshot."""
    limit = threshold(value) if mode == "small" else None
    source = capture(area=mode == "small") if source is None else source
    return apply(source, plan(source.paths, mode, limit))
