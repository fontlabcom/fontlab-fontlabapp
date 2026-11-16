# this_file: src/fontlabapp/components/graph/native.py
# SPDX-License-Identifier: Apache-2.0
"""Read whole-font current-master component names without geometry/cache writers."""

from threading import current_thread, main_thread
from typing import Any

from fontlabapp.glyphs.catalog.native import _check, _context
from fontlabapp.components.graph.elastic.physics import Graph


def _rows(package: Any, font: Any, deadline: float) -> tuple:
    rows, facts, identities, native_ids = [], [], set(), set()
    for source in font.glyphs:
        _check(deadline)
        identity, name = int(source.id), source.name
        if identity in identities or not isinstance(name, str) or not name:
            raise ValueError("A glyph identity/name is duplicated or unreadable.")
        identities.add(identity)
        glyph = package.findFgId(identity)
        if glyph is None or glyph.isNull or not glyph.isValid:
            raise ValueError("A mapped glyph is unavailable; refresh.")
        if (
            int(glyph.fgGlyphId) != identity
            or glyph.name != name
            or int(glyph.package.id) != int(package.id)
        ):
            raise ValueError("Glyph identity or owner changed; refresh.")
        if int(glyph.id) in native_ids:
            raise ValueError("Native glyph identities are duplicated; refresh.")
        native_ids.add(int(glyph.id))
        layer = glyph.findLayer(package.master)
        if layer is None or layer.isNull:
            raise ValueError("A glyph has no current-master layer; no partial graph.")
        bases, shapes = [], []
        for shape in layer.shapes:
            _check(deadline)
            role = shape.isComponent
            if type(role) is not bool:
                raise ValueError("An unreadable shape role prevents component capture.")
            base = shape.shapeData.componentGlyph if role else None
            if role:
                if not isinstance(base, str) or not base:
                    raise ValueError("A component has no readable base name.")
                bases.append(base)
            shapes.append((int(shape.id), role, base))
        rows.append((name, tuple(bases)))
        facts.append((identity, int(glyph.id), int(layer.id), tuple(shapes)))
    _check(deadline)
    return tuple(rows), tuple(facts)


def capture(*, deadline: float) -> Graph:
    """Double-read context, font order and shapes under the caller's shared deadline.

    All glyphs, including unencoded and isolated glyphs, remain in font order.
    Missing references, repeats and cycles remain explicit. Native getter/cache
    preservation is unqualified; no fgGlyph getter or font writer is used.
    """
    if current_thread() is not main_thread():
        raise RuntimeError("Capture component dependencies on the main UI thread.")
    context, package, font = _context(deadline)
    first = _rows(package, font, deadline)
    other, package, font = _context(deadline)
    second = _rows(package, font, deadline)
    final, _, _ = _context(deadline)
    if context != other or other != final or first != second:
        raise ValueError("Font, master or components changed; refresh the graph.")
    return Graph.from_rows(first[0], deadline=deadline)
