# this_file: src/fontlabapp/masters/layers/show_all/native.py
# SPDX-License-Identifier: Apache-2.0
"""All stored foreground layers for each selected parent in a fresh native proof.

No source-index rewrite, Unicode/slash substitution, sorting or deduplication.
Masks/service records are backgrounds. Actual selected-slot/control/role mapping
and complete native read/tab preservation remain qualification requirements.
"""

from dataclasses import dataclass
from time import monotonic
from typing import Any

import fontlabapp.masters.layers.selection as selection
import fontlabapp.proof.tabs.named as tabs
from fontlabapp import _native
from fontlabapp.masters.layers.show_all.model import Group, expand


@dataclass(frozen=True)
class Snapshot:
    """Detached groups and complete selection/layer-domain identity fences."""

    context: tuple
    groups: tuple[Group, ...]
    states: tuple


def check(deadline: float) -> None:
    """One absolute deadline bounds capture, construction and tab creation."""
    if monotonic() >= deadline:
        raise TimeoutError("Show All Layers expired; no complete proof is available.")


def read(selected: Any, deadline: float) -> Snapshot:
    """Keep stored foreground layer order and every selected parent occurrence."""
    groups, states = [], []
    for occurrence in selected.occurrences:
        check(deadline)
        glyph, chosen = occurrence.glyph, occurrence.layer
        if (
            glyph.isNull
            or chosen.isNull
            or int(glyph.package.id) != selected.context[0]
            or int(glyph.id) != occurrence.glyph_id
            or int(chosen.id) != occurrence.layer_id
            or str(glyph.name) != occurrence.glyph_name
            or str(chosen.name) != occurrence.layer_name
        ):
            raise ValueError("A selected parent/layer changed before the proof.")
        names, domain, identifiers = [], [], set()
        for layer in glyph.layers:
            check(deadline)
            if (
                layer.isNull
                or not layer.isValid
                or int(layer.glyph.id) != int(glyph.id)
            ):
                raise ValueError("Invalid or foreign layer prevents a complete proof.")
            identity, name = int(layer.id), str(layer.name)
            roles = (layer.isMasterLayer, layer.isMaskLayer, layer.isService)
            if identity in identifiers or any(type(role) is not bool for role in roles):
                raise ValueError("Ambiguous native layer identity/role.")
            identifiers.add(identity)
            domain.append((identity, name, roles))
            if roles[1] or roles[2]:
                continue
            if not name or name in names or int(glyph.findLayer(name).id) != identity:
                raise ValueError(
                    "Foreground layers need exact unique addressable names."
                )
            names.append(name)
        groups.append(Group(occurrence.glyph_name, tuple(names)))
        states.append((occurrence.glyph_id, tuple(domain)))
    check(deadline)
    return Snapshot(selected.context, tuple(groups), tuple(states))


def capture(deadline: float) -> Snapshot:
    """Double-read complete selected occurrences and every stored layer domain."""
    first = selection.capture(deadline)
    before = read(first, deadline)
    second = selection.capture(deadline)
    repeated = read(second, deadline)
    if (
        first != second
        or before != repeated
        or selection.document_context(deadline) != second.context
    ):
        raise ValueError(
            "Font, selection or layers changed; run Show All Layers again."
        )
    check(deadline)
    return before


def symbols(native: Any, rows: tuple, deadline: float) -> Any:
    """Create exact named layer references and literal newline control symbols."""
    result = native.fgSymbolList("")
    for row in rows:
        check(deadline)
        if row is None:
            result.append(native.fgSymbolList("\n"))
        else:
            name, layer = row
            symbol = native.fgSymbol(name)
            symbol.layerName = layer
            result.append(native.fgSymbolList([symbol]))
    check(deadline)
    return result


def run() -> dict[str, int]:
    """Open a genuine fresh layer-aware proof only after complete revalidation."""
    deadline = monotonic() + 2.0
    before = capture(deadline)
    rows = expand(before.groups)
    if not rows:
        return {"groups": 0, "layers": 0}
    native = _native("fontlab")
    result = symbols(native, rows, deadline)
    if capture(deadline) != before:
        raise ValueError("The complete source changed before tab creation.")
    check(deadline)
    tabs._open_symbols(native, result, before.context[0], before.context[1], deadline)
    return {
        "groups": len(before.groups),
        "layers": sum(row is not None for row in rows),
    }
