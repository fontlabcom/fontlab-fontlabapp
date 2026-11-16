# this_file: src/fontlabapp/qt/painting/view.py
"""View data for one laid-out glyph occurrence: scale, neighbours and cursor.

Used by ``fontlabapp.plugins.backend`` and ``fontlabapp.plugins.tools.bridge``;
``EditorPainters`` computes the same scale as ``PaintContext.scale``.
"""

import math
from collections.abc import Callable
from typing import Any

from fontlabapp.contours import affine

__all__ = ["glyph_point", "neighbours", "px_per_unit"]

#: ``(glyph name, displayed kerning in font units)``, or None.
Side = tuple[str, float] | None


def px_per_unit(
    to_view: Callable[[Any], Any], point_type: Callable[[float, float], Any]
) -> float:
    """Return the view length of one glyph-unit x step through ``to_view``.

    ``to_view`` maps a glyph point through the glyph-item, text-block and
    canvas-viewport maps (b: ``EditorPainters._contexts``). This is not
    ``canvas.scale()``, which omits the glyph and block scale. Raises
    ``ValueError`` when the mapped length is not finite.
    """
    origin, step = to_view(point_type(0.0, 0.0)), to_view(point_type(1.0, 0.0))
    scale = math.hypot(step.x() - origin.x(), step.y() - origin.y())
    if not math.isfinite(scale):
        raise ValueError("Non-finite view scale.")
    return scale


def glyph_point(glyph: Any, block: Any, point: Any) -> tuple[float, float]:
    """Map a canvas-unit ``point`` into glyph units of one occurrence.

    The glyph-item transform, then the text-block transform, maps glyph units
    to canvas units (b: ``EditorPainters``, ``tools.bridge``); this applies
    the inverse. ``canvas.mousePosition()`` is already in canvas units
    (a-src ``flvisual.cpp``); a viewport point needs ``mapFromViewport``
    first. Raises ``ValueError`` for a non-invertible or non-finite map.
    """
    t = affine.concat(affine.from_qtransform(glyph), affine.from_qtransform(block))
    return affine.apply(affine.invert(t), float(point.x()), float(point.y()))


def _side(other: Any, owner: Any) -> Side:
    """Name ``other`` with the kerning stored on ``owner``, in font units."""
    if other is None or other.glyph is None or other.glyph.isNull:
        return None
    scale = float(owner.transform.m11())
    if scale == 0 or not math.isfinite(scale):
        raise ValueError("Unusable glyph scale for displayed kerning.")
    value = float(owner.kerningOffset(True)) / scale
    if not math.isfinite(value):
        raise ValueError("Non-finite displayed kerning.")
    return str(other.glyph.name), value


def neighbours(
    block: Any, index: int, info: Any, report: Callable[[Exception], object]
) -> tuple[Side, Side]:
    """Return ``(prev, next)`` beside paragraph glyph ``index`` (``info``).

    ``block.getPrevGlyphInLine`` / ``getNextGlyphInLine`` take the paragraph
    index and return None across a line break (a-stub; a-src
    ``fltextblock.cpp`` compares ``lineIndex``). Kerning is
    ``kerningOffset(True) / transform.m11()`` (a-src metrics tool): the layout
    value, classes applied, plus any drag offset, in font units; it is 0 when
    the block's ``kerningProcessing`` is off. A mirrored slot (negative
    ``m11``) flips its sign. The pair (prev, this) is read from prev and
    (this, next) from ``info``; that side convention is (c), unverified
    natively. A missing or null neighbour glyph gives None. Each side fails
    alone: an unusable scale, a non-finite kerning or a failing lookup makes
    that side None and goes to ``report``; the other side is kept.
    """
    prev = following = None
    try:
        before = block.getPrevGlyphInLine(index)
        prev = _side(before, before)
    except Exception as error:  # noqa: BLE001 - one side must not drop the other
        report(error)
    try:
        following = _side(block.getNextGlyphInLine(index), info)
    except Exception as error:  # noqa: BLE001 - one side must not drop the other
        report(error)
    return prev, following
