# this_file: src/fontlabapp/masters/node_report/native.py
# SPDX-License-Identifier: Apache-2.0
"""Capture selected unique glyphs' complete ordered master domain, never auxiliaries."""

from time import monotonic
from typing import Any

import fontlabapp.masters.layers.selection as selection
from fontlabapp.masters.layers.compatibility import _records as records
from fontlabapp.masters.layers.compatibility.model import GlyphLayers, Layer


def _master(glyph: Any, name: str, deadline: float) -> tuple:
    """Resolve only a named master; read own contours, not unrelated metadata."""
    layer = glyph.findLayer(name)
    if (
        layer is None
        or layer.isNull
        or not layer.isValid
        or layer.glyph.id != glyph.id
        or layer.name != name
        or layer.isMasterLayer is not True
        or layer.isMaskLayer is not False
        or layer.isService is not False
    ):
        raise ValueError("A selected glyph is missing a valid master layer.")
    paths, states = [], []
    for shape in layer.shapes:
        records.check(deadline)
        component = shape.isComponent
        if type(component) is not bool:
            raise ValueError("Unreadable master shape role.")
        if component:
            states.append((int(shape.id), True))
            continue
        if shape.isComposite:
            raise ValueError(
                "Generated master shapes need native topology qualification."
            )
        contours = []
        for contour in shape.contours:
            records.check(deadline)
            kinds, state = records.nodes(contour, deadline)
            paths.append(kinds)
            contours.append(state)
        states.append((int(shape.id), False, tuple(contours)))
    records.check(deadline)
    return Layer(name, tuple(paths)), (int(layer.id), name, tuple(states))


def _read(selected: selection.LayerSelection, deadline: float) -> tuple:
    """Capture required masters only; never enumerate glyph.layers or anchors."""
    result = []
    for occurrence in selected.occurrences:
        records.check(deadline)
        glyph, chosen, package = occurrence.glyph, occurrence.layer, occurrence.package
        if (
            glyph.isNull
            or chosen.isNull
            or int(glyph.id) != occurrence.glyph_id
            or int(chosen.id) != occurrence.layer_id
            or str(glyph.name) != occurrence.glyph_name
            or str(chosen.name) != occurrence.layer_name
            or int(glyph.package.id) != occurrence.package_id
            or int(package.id) != occurrence.package_id
            or package.master != selected.context[1]
        ):
            raise ValueError("Selected glyph/layer/font/master changed; refresh.")
        masters = tuple(package.masters)
        if (
            not masters
            or any(not isinstance(n, str) or not n for n in masters)
            or len(set(masters)) != len(masters)
            or package.master not in masters
        ):
            raise ValueError("Unreadable native master domain.")
        rows = tuple(_master(glyph, name, deadline) for name in masters)
        identities = tuple(row[1][0] for row in rows)
        if len(set(identities)) != len(identities):
            raise ValueError("Duplicate native master layer identity.")
        result.append(
            (
                int(glyph.id),
                masters,
                tuple(row[1] for row in rows),
                GlyphLayers(occurrence.glyph_name, tuple(row[0] for row in rows)),
            )
        )
    records.check(deadline)
    return tuple(result)


def capture() -> tuple[GlyphLayers, ...]:
    """Fence full domains twice and selection three times within two seconds.

    Reuse source-level node-type mapping, not the adjacent-layer reader/verdict.
    Actual native read preservation remains pending; no getter is assumed pure.
    """
    deadline = monotonic() + 2.0
    first = selection.capture(deadline)
    if not first.occurrences:
        raise ValueError("No glyph selected.")
    rows = _read(first, deadline)
    second = selection.capture(deadline)
    repeated = _read(second, deadline)
    final = selection.capture(deadline)
    context = selection.document_context(deadline)
    records.check(deadline)
    if (
        first != second
        or second != final
        or rows != repeated
        or final.context != context
    ):
        raise ValueError("Font, selection, masters or topology changed; refresh.")
    result, seen = [], set()
    for identifier, masters, _, group in rows:
        if identifier in seen:
            continue
        seen.add(identifier)
        layers = {layer.name: layer for layer in group.layers}
        if any(master not in layers for master in masters):
            raise ValueError(
                "A selected glyph is missing a master layer; no partial report."
            )
        result.append(GlyphLayers(group.name, tuple(layers[name] for name in masters)))
    return tuple(result)
