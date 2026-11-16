# this_file: src/fontlabapp/guides/perpendicular/selection.py
# SPDX-License-Identifier: Apache-2.0
"""First selected layer only, retaining the maintained native carrier boundaries.

Do not eagerly resolve later selected glyphs/layers: they are outside this
original action's domain. Actual native carrier/slot mapping remains qualified
separately. No ordinal fallback, selection writer or legacy font activation.
"""

from importlib import import_module
from time import monotonic
from typing import Any

from fontlabapp import _native
from fontlabapp.core.scripting import _carrier_id

reader = import_module("fontlabapp.masters.layers.selection")


def check(deadline: float) -> None:
    """One absolute bound covers both first-target reads and source fencing."""
    if monotonic() >= deadline:
        raise TimeoutError("First selected layer capture exceeded its deadline.")


def first_font(document: Any, deadline: float) -> tuple:
    """Short-circuit native font-order selection before any later model lookup."""
    fl = _native("FL").fl
    font = fl.font
    if font is None or _carrier_id(font, int(document.package.fgId)) != int(document.package.fgId):
        raise ValueError("Font-window carrier differs from the active package.")
    for index in range(len(font)):
        check(deadline)
        if fl.Selected(index):
            glyph = document.package.findName(font[index].name)
            layer = None if glyph is None else glyph.findLayer(document.context[1])
            row = reader._occurrence(document.package, glyph, layer, 0, index)
            if fl.font is None or _carrier_id(fl.font, int(document.package.fgId)) != int(document.package.fgId):
                raise ValueError("Font-window carrier changed during capture.")
            return (row,)
    return ()


def first_editor(document: Any, deadline: float) -> tuple:
    """Keep existing selected/active slot rules; stop after the first owner."""
    for block in document.blocks:
        check(deadline)
        for index in range(int(block.glyphsCount())):
            check(deadline)
            info = block.getGlyphAt(index)
            if info is None or not (info.isSelected or info.isActive):
                continue
            glyph = info.glyph
            if glyph is None or glyph.isNull:
                raise ValueError("The first selected editor slot has no glyph.")
            name = str(info.symbol.layerName)
            layer = glyph.findLayer(name) if name else glyph.activeLayer
            return (
                reader._occurrence(
                    document.package, glyph, layer, int(block.id), index
                ),
            )
    return ()


def read(deadline: float) -> Any:
    """Resolve one original target while retaining known document owner wrappers."""
    check(deadline)
    document = reader._document(deadline)
    rows = (first_font if document.context[2] == "font" else first_editor)(
        document, deadline
    )
    check(deadline)
    return reader.LayerSelection(document.context[:4], rows, document.carriers)


def capture(deadline: float) -> Any:
    """Fence first-layer identity/context twice without expanding its scope."""
    first, second = read(deadline), read(deadline)
    if first != second or second.context != reader._document(deadline).context[:4]:
        raise ValueError("First selected layer or its document changed; run again.")
    check(deadline)
    return second
