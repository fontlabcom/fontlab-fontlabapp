# this_file: src/fontlabapp/masters/background/selection.py
# SPDX-License-Identifier: Apache-2.0
"""First selected foreground layer only for the original all-font replacement."""

from typing import Any

import fontlabapp.masters.layers.selection as layers
from fontlabapp import _native


def read(deadline: float) -> Any:
    """Resolve only the first selected layer; never inspect later slot layers."""
    layers._check(deadline)
    workspace = _native("fontlab").flWorkspace.instance()
    package = workspace.currentPackage
    if package is None or package.isNull:
        raise ValueError("Open a font and select a foreground layer.")
    base = (int(package.id), str(package.master))
    panel = workspace.activeFontPanel
    if panel is not None:
        layers._require_selection_window(base[0])
        context = (*base, "font", id(panel))
        names = layers.names_font_window_selection(
            expected_fg_id=int(package.fgId), deadline=deadline
        )
        if not names:
            return layers.LayerSelection(context, (), (panel,))
        glyph = package.findName(names[0])
        layer = None if glyph is None else glyph.findLayer(base[1])
        return layers.LayerSelection(
            context, (layers._occurrence(package, glyph, layer, 0, 0),), (panel,)
        )
    canvas = workspace.getActiveCanvas()
    if canvas is None or canvas.isNull:
        raise ValueError("Activate a Glyph window to read the selected source layer.")
    parents = layers._glyph_window(canvas.viewPort)
    blocks = tuple(layers.qt_list(canvas.textBlocks))
    context = (*base, "editor", int(canvas.id))
    carriers = (canvas, *parents, *blocks)
    for block in blocks:
        layers._check(deadline)
        for index in range(int(block.glyphsCount())):
            layers._check(deadline)
            info = block.getGlyphAt(index)
            if info is None or not (info.isSelected or info.isActive):
                continue
            glyph = info.glyph
            if glyph is None or glyph.isNull:
                raise ValueError("The first selected glyph is missing.")
            name = str(info.symbol.layerName)
            layer = glyph.findLayer(name) if name else glyph.activeLayer
            return layers.LayerSelection(
                context,
                (layers._occurrence(package, glyph, layer, int(block.id), index),),
                carriers,
            )
    return layers.LayerSelection(context, (), carriers)


def capture(deadline: float) -> Any:
    """Fence first occurrence and relevant context without resolving later layers."""
    first, second = read(deadline), read(deadline)
    if first != second:
        raise ValueError("First selected foreground layer changed; run again.")
    layers._check(deadline)
    return second
