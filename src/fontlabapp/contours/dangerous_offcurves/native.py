# this_file: src/fontlabapp/contours/dangerous_offcurves/native.py
# SPDX-License-Identifier: Apache-2.0 AND MIT
"""Read the entire current font and open every distinct problematic exact layer.

Reuse established current-font identity, raw node roles and layer-aware tab
transport. Never clone/decompose, read flGlyph.fgGlyph, or edit a font. Native
getter/cache and exact layer transport preservation still require qualification.
"""

from dataclasses import dataclass
from math import isfinite
from threading import current_thread, main_thread
from time import monotonic
from typing import Any

import fontlabapp.masters.layers.brackets._snapshot as source
import fontlabapp.masters.layers.compatibility._records as records
import fontlabapp.contours.dangerous_offcurves.model as model
import fontlabapp.proof.tabs.named as tabs


@dataclass(frozen=True)
class Snapshot:
    """Complete immutable geometry and identity facts; no live native handles."""

    context: tuple
    layers: tuple[model.Layer, ...]
    facts: tuple


def _paths(layer: Any, deadline: float) -> tuple:
    """Keep every own node in layer coordinates, including wrapped source windows."""
    paths, facts = [], []
    for shape in layer.shapes:
        model.check(deadline)
        component = shape.isComponent
        if type(component) is not bool:
            raise ValueError("Unreadable shape role; no partial result.")
        if component:
            facts.append((int(shape.id), True))
            continue
        transform = shape.transform
        matrix = tuple(
            getattr(transform, f"m{i}{j}")() for i in (1, 2, 3) for j in (1, 2, 3)
        )
        if not all(isfinite(v) for v in matrix) or (
            matrix[2],
            matrix[5],
            matrix[8],
        ) != (0, 0, 1):
            raise ValueError("Projective/nonfinite shapes need geometry qualification.")
        contours = []
        for contour in shape.contours:
            model.check(deadline)
            kinds, state = records.nodes(contour, deadline)
            points, ids = [], []
            for node in contour.nodes():
                model.check(deadline)
                point = transform.map(node.position)
                x, y = point.x(), point.y()
                if not isfinite(x) or not isfinite(y):
                    raise ValueError(
                        "Nonfinite node coordinates prevent a complete scan."
                    )
                points.append((x, y))
                ids.append(int(node.id))
            if tuple(ids) != tuple(item[0] for item in state[3]):
                raise ValueError("Contour node identities changed while reading.")
            if state[1] and points:
                points = points[1:] + points[:1]
            paths.append(
                tuple(
                    model.Node(x, y, kind == "offcurve")
                    for (x, y), kind in zip(points, kinds, strict=True)
                )
            )
            contours.append((state, tuple(points)))
        facts.append((int(shape.id), False, matrix, tuple(contours)))
    model.check(deadline)
    return tuple(paths), tuple(facts)


def _read(package: Any, font: Any, deadline: float) -> tuple:
    """Traverse every glyph and stored foreground layer without selected subsets."""
    layers, facts, seen = [], [], set()
    for item in font.glyphs:
        model.check(deadline)
        fid, name = int(item.id), item.name
        glyph = package.findFgId(fid)
        if (
            fid in seen
            or glyph is None
            or glyph.isNull
            or not glyph.isValid
            or int(glyph.fgGlyphId) != fid
            or int(glyph.package.id) != int(package.id)
            or glyph.name != name
            or not isinstance(name, str)
            or not name
        ):
            raise ValueError("Current-font glyph identity/name/owner is ambiguous.")
        seen.add(fid)
        domain = []
        layer_ids = set()
        for layer in glyph.layers:
            model.check(deadline)
            roles = layer.isMaskLayer, layer.isService
            if (
                layer.isNull
                or not layer.isValid
                or int(layer.glyph.id) != int(glyph.id)
                or any(type(v) is not bool for v in roles)
                or int(layer.id) in layer_ids
                or not isinstance(layer.name, str)
            ):
                raise ValueError("A layer identity/name/role is unreadable or changed.")
            layer_ids.add(int(layer.id))
            paths, state = ((), ()) if any(roles) else _paths(layer, deadline)
            domain.append((int(layer.id), layer.name, roles, state))
            if not any(roles):
                layers.append(
                    model.Layer((int(glyph.id), int(layer.id)), name, layer.name, paths)
                )
        facts.append((fid, int(glyph.id), name, tuple(domain)))
    model.check(deadline)
    return tuple(layers), tuple(facts)


def capture(deadline: float) -> Snapshot:
    """Double-read the complete font, with exact context and geometry fences."""
    if current_thread() is not main_thread():
        raise RuntimeError("Run Dangerous Offcurves on the main UI thread.")
    context, package, font = source._current(deadline)
    before = _read(package, font, deadline)
    other, package, font = source._current(deadline)
    after = _read(package, font, deadline)
    final, _, _ = source._current(deadline)
    model.check(deadline)
    if context != other or other != final or before != after:
        raise ValueError("Font, layers or geometry changed; run the scan again.")
    return Snapshot(context, *before)


def _targets(
    snapshot: Snapshot, result: model.Report, package: Any, deadline: float
) -> tuple:
    """Validate every winning glyph/layer name resolves its exact captured identity."""
    rows = []
    for identity in result.layers:
        model.check(deadline)
        row = next(layer for layer in snapshot.layers if layer.identity == identity)
        glyph = package.findName(row.glyph)
        layer = None if glyph is None else glyph.findLayer(row.name)
        if (
            not row.name
            or glyph is None
            or int(glyph.id) != identity[0]
            or layer is None
            or int(layer.id) != identity[1]
        ):
            raise ValueError("A winning layer lacks an exact addressable native name.")
        rows.append((row.glyph, row.name))
    return tuple(rows)


def run(*, deadline: float | None = None) -> model.Report:
    """Analyse the whole font and automatically open a genuine exact-layer tab.

    One ten-second Python checkpoint budget covers all scans/analysis/tab creation.
    Blocking native calls cannot be preempted. Tab creation failure can leave a
    new owned UI tab; no atomic UI rollback or native acceptance is claimed.
    """
    limit = monotonic() + 10 if deadline is None else deadline
    before = capture(limit)
    result = model.analyse(before.layers, deadline=limit)
    if capture(limit) != before:
        raise ValueError("The complete source font changed during analysis.")
    context, package, _ = source._current(limit)
    if context != before.context:
        raise ValueError("Source font changed before proof creation.")
    rows = _targets(before, result, package, limit)
    model.check(limit)
    if rows:
        tabs.open_layer_tab(
            rows, expected_id=context[0], master=context[2], deadline=limit
        )
    return result
