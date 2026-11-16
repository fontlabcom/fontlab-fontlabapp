# this_file: src/fontlabapp/glyphs/others.py
"""Find another glyph's layer by name without creating either, read-only.

Evidence: ``package.findName(name)`` and ``glyph.findLayer(name)`` (a-stub;
b: ``components.decompose``, Glyport ``native_reference``). Used by
``fontlabapp.plugins.snapshot.capture`` for reporters' requested glyphs;
``findLayerCreate`` and ``getLayerByName`` are never called.
"""

from typing import Any

__all__ = ["find"]


def find(package: Any, name: str, master: str) -> tuple[Any, Any] | None:
    """Return ``(glyph, layer)`` for glyph ``name``'s ``master`` layer, or None.

    None means the glyph or that layer does not exist (or is null); that is
    absence, not an error. Missing native attributes raise.
    """
    glyph = package.findName(name)
    if glyph is None or glyph.isNull:
        return None
    layer = glyph.findLayer(master)
    if layer is None or layer.isNull:
        return None
    return glyph, layer
