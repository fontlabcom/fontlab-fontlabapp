# this_file: src/fontlabapp/masters/layers/brackets/_snapshot.py
# SPDX-License-Identifier: Apache-2.0
"""Read the entire current font's foreground names and direct component edges.

Use CurrentFont().glyphs for FontGate identities, then bound findFgId. Never
read flGlyph.fgGlyph, enumerate property values, inspect geometry, pump events
or write native state. Cold/lazy getter side effects remain a native gate.
"""

from dataclasses import dataclass
from threading import current_thread, main_thread
from time import monotonic
from typing import Any

from fontlabapp import _native
from fontlabapp.masters.layers.brackets.model import Glyph


@dataclass(frozen=True)
class Snapshot:
    """Complete immutable graph plus observed identity facts; no live handles."""

    context: tuple[int, int, str]
    glyphs: tuple[Glyph, ...]
    facts: tuple


def check(deadline: float) -> None:
    if monotonic() >= deadline:
        raise TimeoutError("Bracket-layer scan expired; no partial result.")


def _current(deadline: float) -> tuple:
    check(deadline)
    native = _native("fontlab")
    package = native.flWorkspace.instance().currentPackage
    if package is None or package.isNull:
        raise ValueError("No font is open. Please open a font and try again.")
    font = native.CurrentFont()
    if font is None or int(font.id) != int(package.fgId):
        raise ValueError("Current native font identity changed or is unreadable.")
    master = package.master
    if not isinstance(master, str):
        raise TypeError("The source master name is unreadable.")
    return (int(package.id), int(package.fgId), master), package, font


def _shapes(layer: Any, deadline: float) -> tuple:
    bases, facts, ids = set(), [], set()
    for shape in layer.shapes:
        check(deadline)
        identifier = int(shape.id)
        flags = shape.isComponent, shape.isComposite
        if identifier in ids or any(type(v) is not bool for v in flags):
            raise ValueError("Duplicate or unreadable native shape identity/role.")
        ids.add(identifier)
        component, composite = flags
        if composite and not component:
            raise ValueError(
                "Generated composite shapes need native dependency qualification."
            )
        base = shape.shapeData.componentGlyph if component else None
        if component:
            if not isinstance(base, str):
                raise TypeError("A component has no readable base name.")
            bases.add(base)
        facts.append((identifier, flags, base))
    return frozenset(bases), tuple(facts)


def _layers(glyph: Any, deadline: float) -> tuple:
    names, bases, facts, ids = [], set(), [], set()
    for layer in glyph.layers:
        check(deadline)
        if (
            layer is None
            or layer.isNull
            or not layer.isValid
            or int(layer.glyph.id) != int(glyph.id)
        ):
            raise ValueError("A glyph has an invalid or foreign layer.")
        identifier, name = int(layer.id), layer.name
        roles = layer.isMaskLayer, layer.isService
        if (
            identifier in ids
            or not isinstance(name, str)
            or any(type(v) is not bool for v in roles)
        ):
            raise ValueError("Duplicate or unreadable layer identity/name/role.")
        ids.add(identifier)
        state = ()
        if not any(roles):
            components, state = _shapes(layer, deadline)
            names.append(name)
            bases.update(components)
        facts.append((identifier, name, roles, state))
    return tuple(names), frozenset(bases), tuple(facts)


def _read(package: Any, font: Any, deadline: float) -> tuple:
    result, facts, fg_ids, native_ids, names = [], [], set(), set(), set()
    for source in font.glyphs:
        check(deadline)
        identity, name = int(source.id), source.name
        if identity in fg_ids or name in names:
            raise ValueError("Duplicate glyph identity/name makes the font ambiguous.")
        fg_ids.add(identity)
        names.add(name)
        glyph = package.findFgId(identity)
        if glyph is None or glyph.isNull or not glyph.isValid:
            raise ValueError("A native glyph is missing or invalid.")
        native_id = int(glyph.id)
        if (
            native_id in native_ids
            or int(glyph.fgGlyphId) != identity
            or int(glyph.package.id) != int(package.id)
            or glyph.name != name
        ):
            raise ValueError("Native glyph identity, source owner or name changed.")
        native_ids.add(native_id)
        layers, bases, state = _layers(glyph, deadline)
        result.append(Glyph(name, layers, bases))
        facts.append((identity, native_id, name, state))
    check(deadline)
    return tuple(result), tuple(facts)


def capture(*, deadline: float | None = None) -> Snapshot:
    """Double-read every glyph under one2sbudget; refuse any changed prefix.

    This fences observed graph/context facts, not arbitrary font metadata or an
    atomic native transaction. A blocking native getter cannot be preempted.
    """
    if current_thread() is not main_thread():
        raise RuntimeError("Run the bracket-layer workflow on the main UI thread.")
    limit = monotonic() + 2.0 if deadline is None else deadline
    context, package, font = _current(limit)
    first = _read(package, font, limit)
    repeated, other_package, other_font = _current(limit)
    second = _read(other_package, other_font, limit)
    final, _, _ = _current(limit)
    check(limit)
    if context != repeated or repeated != final or first != second:
        raise ValueError(
            "Font, layer names or component dependencies changed; refresh."
        )
    return Snapshot(context, *first)


def validate(snapshot: Snapshot, deadline: float) -> None:
    """Recheck the full graph before the shared backend may open a fresh tab."""
    context, package, font = _current(deadline)
    rows = _read(package, font, deadline)
    final, _, _ = _current(deadline)
    check(deadline)
    if (
        context != snapshot.context
        or final != context
        or rows != (snapshot.glyphs, snapshot.facts)
    ):
        raise ValueError(
            "The captured font, layer names or component dependencies changed."
        )
