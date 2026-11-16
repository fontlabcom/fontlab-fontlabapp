# this_file: src/fontlabapp/core/sharing.py
# SPDX-License-Identifier: Apache-2.0
"""Whether an edit to a shape's contours would change another glyph's outline.

What: ``element_shared(shape, layer)`` is True only when the shape's
``shapeData.referenceCount`` exceeds 1 plus the component shapes that use
this glyph's same-name layer; ``sharing_operation()`` memoises the user counts
for one scan, plan or apply pass.
Why: FontLab counts every component shape that points at a glyph's layer in
the element's reference count (a plain ``a`` used by 33 composites reads 34;
on Lato Hairline a composite holding two ``acute`` components adds two).
Those composites re-render from the base glyph, so they are not shared outline
data. The raw ``referenceCount > 1`` test refused every component base.
Studios (``fontlabapp.studios``) and ``fontlabapp.contours.writer`` both use
these names; the writer re-exports them.
Safety: reads only. When the glyph, layer or package cannot be resolved, the
answer stays the conservative ``referenceCount > 1`` and the reason is logged
at debug level.

Counting users reads one layer of every glyph (about 0.05 s per master in a
3000-glyph font). Inside ``sharing_operation()`` the counts are memoised per
(package id, layer name) and dropped on exit, so no cache outlives an edit.
The memo assumes the pass does not add or remove components while it is
active, and it is module-global, so use it from the FontLab main thread only.
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

LOG = logging.getLogger(__name__)

_memo: dict[tuple[int, str], dict[str, int]] | None = None


@contextmanager
def sharing_operation() -> Iterator[None]:
    """Memoise component-user counts for one scan, planning or apply pass."""
    global _memo
    outer = _memo
    if outer is None:
        _memo = {}
    try:
        yield
    finally:
        if outer is None:
            _memo = None


def _name(value: Any) -> str:
    """Return a name from a ``str`` or an object with ``.name``."""
    if value is None:
        return ""
    name = getattr(value, "name", value)
    return str(name() if callable(name) else name)


def _users(package: Any, layer_name: str) -> dict[str, int]:
    """Count component shapes per base glyph on ``layer_name`` of ``package``."""
    counts: dict[str, int] = {}
    for record in package.fgPackage.glyphs:
        glyph = package.findName(str(record.name))
        layer = glyph.findLayer(layer_name) if glyph is not None else None
        for shape in layer.shapes if layer is not None else ():
            if not shape.isComponent:
                continue
            data = shape.shapeData
            target = _name(getattr(data, "componentLayer", None)) or layer_name
            if target == layer_name:
                base = _name(data.componentGlyph)
                counts[base] = counts.get(base, 0) + 1
    return counts


def _component_users(package: Any, glyph_name: str, layer_name: str) -> int:
    """Return how many component shapes use ``glyph_name`` on ``layer_name``."""
    key = (int(package.id), layer_name)
    if _memo is not None and key in _memo:
        return _memo[key].get(glyph_name, 0)
    counts = _users(package, layer_name)
    if _memo is not None:
        _memo[key] = counts
    return counts.get(glyph_name, 0)


def element_shared(shape: Any, layer: Any = None, package: Any = None) -> bool:
    """Return True when editing ``shape``'s contours would change another glyph.

    True only when ``referenceCount`` exceeds 1 plus the component shapes that
    use this glyph's same-name layer. When ``layer``, its glyph or ``package``
    cannot be resolved, fall back to the conservative ``referenceCount > 1``.
    """
    references = int(shape.shapeData.referenceCount)
    if references <= 1:
        return False
    try:
        glyph = layer.glyph
        package = package if package is not None else glyph.package
        users = _component_users(package, _name(glyph), _name(layer))
    except Exception:  # unresolvable context stays conservative; logged at debug
        LOG.debug("component users not counted; shape kept as shared", exc_info=True)
        return True
    return references > 1 + users


__all__ = ["element_shared", "sharing_operation"]
