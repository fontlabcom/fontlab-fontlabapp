# this_file: src/fontlabapp/glyphs/background.py
"""Read the displayed layer's background (mask) contours without creating one.

Evidence classes follow Issue 209 ``native-data-map.md`` §2:
``layer.getMaskLayer(False)`` returns the mask or None (a-stub, b: App's
background capture, Glyport ``background_layer``); ``isMaskLayer`` is a plain
bool (a-src, agent-reference 9784). Asking a mask for its mask reverses
direction (b), so a displayed mask layer has no background here. Used by
``fontlabapp.plugins.snapshot.capture``; ``getMaskLayer(True)`` is never called.
"""

from collections.abc import Callable
from typing import Any

__all__ = ["read"]


def read(
    glyph: Any,
    layer: Any,
    contours: Callable[[Any], tuple[Any, ...]],
    report: Callable[[Exception], object],
) -> tuple[Any, ...] | None:
    """Return the mask's contours, ``()`` for an empty mask, or None.

    None means no usable background: the layer is itself a mask, it has no
    valid mask, or the mask belongs to another glyph or is automatic (as App's
    background capture refuses); those last two are reported, not raised.
    """
    if layer.isMaskLayer:
        return None
    mask = layer.getMaskLayer(False)
    if mask is None or mask.isNull or not mask.isValid:
        return None
    if int(mask.glyph.id) != int(glyph.id) or mask.autoLayer:
        report(ValueError("Background skipped: it is automatic or owned elsewhere."))
        return None
    return contours(mask)
