# this_file: src/fontlabapp/masters/layers/compatibility/native.py
# SPDX-License-Identifier: MIT
"""Capture all foreground layer diagnostics for every selected occurrence.

Keep Glyphs2.5 master-first/auxiliary order. Native getters can complete lazy
imports; read/cache/full-font preservation is unqualified. No Output, selection,
master, geometry, history, preference, fgGlyph or UpdateAll writer/getter runs.
"""

from time import monotonic
from typing import Any

import fontlabapp.masters.layers.compatibility._records as records
import fontlabapp.masters.layers.selection as selection
from fontlabapp.masters.layers.compatibility.model import GlyphLayers


def _layers(glyph: Any, masters: tuple[str, ...], deadline: float) -> tuple:
    """Read every present foreground layer; retain mask/service identity fences."""
    foreground, domain, ids = {}, [], set()
    for layer in glyph.layers:
        records.check(deadline)
        if (
            layer is None
            or layer.isNull
            or not layer.isValid
            or layer.glyph.id != glyph.id
        ):
            raise ValueError("A glyph has an invalid or foreign layer.")
        identifier, name = int(layer.id), layer.name
        roles = (layer.isMasterLayer, layer.isMaskLayer, layer.isService)
        if (
            identifier in ids
            or not isinstance(name, str)
            or any(type(v) is not bool for v in roles)
        ):
            raise ValueError("Unreadable or duplicate layer identity/role.")
        ids.add(identifier)
        master, mask, service = roles
        if mask or service:
            domain.append((identifier, name, roles, None))
            continue
        if name in foreground or (master != (name in masters)):
            raise ValueError("Ambiguous foreground master/layer mapping.")
        row, state = records.layer(layer, deadline)
        foreground[name] = row
        domain.append((identifier, name, roles, state))
    names = tuple(n for n in masters if n in foreground) + tuple(
        n for n in foreground if n not in masters
    )
    if not names:
        raise ValueError("A glyph has no reportable foreground layer.")
    return tuple(foreground[n] for n in names), tuple(domain)


def _read(selected: selection.LayerSelection, deadline: float) -> tuple:
    """Preserve repeated selected groups; read native master names per group."""
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
            raise ValueError(
                "Selected source glyph/layer/font/master changed; refresh."
            )
        masters = tuple(package.masters)
        if (
            not masters
            or any(not isinstance(n, str) or not n for n in masters)
            or len(set(masters)) != len(masters)
            or package.master not in masters
        ):
            raise ValueError("Unreadable native master domain.")
        layers, domain = _layers(glyph, masters, deadline)
        result.append(
            (int(glyph.id), masters, domain, GlyphLayers(occurrence.glyph_name, layers))
        )
    records.check(deadline)
    return tuple(result)


def capture() -> tuple[GlyphLayers, ...]:
    """Double-read complete domains under one2sdeadline; refuse stale prefixes.

    Selection and context are captured again after both content reads. Repeated
    selected slots remain repeated; no current-glyph fallback or deduplication.
    Final observed-fact equality is a fence, not an atomic native transaction.
    """
    deadline = monotonic() + 2.0
    first = selection.capture(deadline)
    if not first.occurrences:
        raise ValueError("Select glyph layers before checking compatibility.")
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
        raise ValueError("Font, selection, masters or layer topology changed; refresh.")
    return tuple(row[3] for row in rows)
