# this_file: src/fontlabapp/contours/point_counts/native.py
# SPDX-License-Identifier: Apache-2.0
"""Capture Point Counter values through native readers, without font writers.

Keep every foreground layer in stored order; masks and service layers are
background/cache records. Native getter preservation and role/order mapping
still need owned FontLab qualification. See NOTICE for source provenance.
"""

from time import monotonic
from typing import Any

import fontlabapp.masters.layers.selection as selection
from fontlabapp.contours.point_counts.model import (
    Counts,
    GlyphCount,
    LayerCount,
    render,
)  # noqa: F401


def _check(deadline: float) -> None:
    """Refuse overruns at Python checkpoints rather than publish a prefix."""
    if monotonic() >= deadline:
        raise TimeoutError("Point count exceeded its deadline; no partial report.")


def _nodes(contour: Any, deadline: float) -> tuple[Counts, tuple]:
    """Classify cubic controls and quadratic handles before curve endpoints."""
    closed = bool(contour.closed)
    kinds = []
    for node in contour.nodes():
        _check(deadline)
        if node.isNull:
            raise ValueError("A contour contains a null node; no partial report.")
        control = bool(node.isOff() or node.isCurve())
        if not control and not node.isOn():
            raise ValueError("A contour has an unknown node type; no partial report.")
        kinds.append((int(node.id), control))
    handles = sum(control for _, control in kinds)
    curves = sum(
        not control and (index > 0 or closed) and kinds[index - 1][1]
        for index, (_, control) in enumerate(kinds)
    )
    _check(deadline)
    return (
        Counts(len(kinds) - handles - curves, curves, handles, 1),
        (int(contour.id), closed, tuple(kinds)),
    )


def _layer(layer: Any, deadline: float) -> tuple[LayerCount, tuple]:
    """Count own paths, including empty paths; never decompose components."""
    lines = curves = handles = paths = 0
    shapes = []
    for shape in layer.shapes:
        _check(deadline)
        component = bool(shape.isComponent)
        contours = []
        if not component:
            if shape.isComposite:
                raise ValueError("Nested generated shapes need native qualification.")
            for contour in shape.contours:
                _check(deadline)
                count, state = _nodes(contour, deadline)
                lines += count.lines
                curves += count.curves
                handles += count.handles
                paths += count.paths
                contours.append(state)
        shapes.append((int(shape.id), component, tuple(contours)))
    _check(deadline)
    return LayerCount(str(layer.name), Counts(lines, curves, handles, paths)), tuple(
        shapes
    )


def _read(selected: selection.LayerSelection, deadline: float) -> tuple:
    """Preserve repeated groups and complete stored foreground-layer domains."""
    groups = []
    for occurrence in selected.occurrences:
        _check(deadline)
        glyph, chosen = occurrence.glyph, occurrence.layer
        if (
            glyph.isNull
            or chosen.isNull
            or int(glyph.id) != occurrence.glyph_id
            or int(chosen.id) != occurrence.layer_id
            or str(glyph.name) != occurrence.glyph_name
            or str(chosen.name) != occurrence.layer_name
            or int(glyph.package.id) != occurrence.package_id
        ):
            raise ValueError("A selected glyph/layer identity changed; refresh.")
        layers, states = [], []
        for layer in glyph.layers:
            _check(deadline)
            if not layer.isValid:
                raise ValueError("An invalid glyph layer prevents a complete report.")
            mask, service = bool(layer.isMaskLayer), bool(layer.isService)
            state = (int(layer.id), str(layer.name), mask, service)
            if mask or service:
                states.append((state, None))
                continue
            count, shapes = _layer(layer, deadline)
            layers.append(count)
            states.append((state, shapes))
        groups.append(
            (
                occurrence.glyph_id,
                tuple(states),
                GlyphCount(occurrence.glyph_name, tuple(layers)),
            )
        )
    _check(deadline)
    return tuple(groups)


def capture() -> tuple[GlyphCount, ...]:
    """Double-read counts and fence selection/context under one two-second limit.

    No current-glyph fallback, sorting, deduplication, font mutation or partial
    prefix. Blocking native getters cannot be preempted. Actual native order,
    role mapping, preservation and widget lifetime acceptance remain pending.
    """
    deadline = monotonic() + 2.0
    first = selection.capture(deadline)
    if not first.occurrences:
        raise ValueError("Select glyph layers before counting points.")
    rows = _read(first, deadline)
    second = selection.capture(deadline)
    repeated = _read(second, deadline)
    final = selection.capture(deadline)
    context = selection.document_context(deadline)
    _check(deadline)
    if (
        first != second
        or second != final
        or rows != repeated
        or context != final.context
    ):
        raise ValueError(
            "Font, selection, layers or nodes changed; refresh the report."
        )
    return tuple(row[2] for row in rows)
