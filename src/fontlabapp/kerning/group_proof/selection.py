# this_file: src/fontlabapp/kerning/group_proof/selection.py
# SPDX-License-Identifier: Apache-2.0
"""Read only the first selected glyph parent; never resolve a selected layer."""

from dataclasses import dataclass, field
from typing import Any

import fontlabapp.masters.layers.selection as layers
from fontlabapp import _native


@dataclass(frozen=True)
class First:
    """First parent identity and source context, retaining native wrapper owners."""

    context: tuple
    glyph_id: int
    glyph_name: str
    block_id: int
    index: int
    package: Any = field(compare=False)
    carriers: tuple = field(default=(), compare=False, repr=False)


def _document(deadline: float) -> Any:
    """Capture package/window context without reading unvisited block IDs."""
    layers._check(deadline)
    workspace = _native("fontlab").flWorkspace.instance()
    package = workspace.currentPackage
    if package is None or package.isNull:
        raise ValueError("Open a font before reading the first selected glyph.")
    base = (int(package.id), str(package.master))
    panel = workspace.activeFontPanel
    if panel is not None:
        layers._require_selection_window(base[0])
        return layers._Document((*base, "font", id(panel)), package, carriers=(panel,))
    canvas = workspace.getActiveCanvas()
    if canvas is None or canvas.isNull:
        raise ValueError(
            "Activate a Glyph window before reading the first selected glyph."
        )
    parents = layers._glyph_window(canvas.viewPort)
    blocks = tuple(layers.qt_list(canvas.textBlocks))
    layers._check(deadline)
    return layers._Document(
        (*base, "editor", int(canvas.id)), package, blocks, (canvas, *parents, *blocks)
    )


def _parent(document: Any, glyph: Any, block_id: int, index: int) -> First:
    if (
        glyph is None
        or glyph.isNull
        or int(glyph.package.id) != int(document.package.id)
    ):
        raise ValueError(
            "The first selected glyph is missing or belongs to another font."
        )
    return First(
        document.context,
        int(glyph.fgGlyphId),
        str(glyph.name),
        block_id,
        index,
        document.package,
        document.carriers,
    )


def read(deadline: float) -> First | None:
    """Use existing native selection order, stopping before every later parent.

    Font-window selection names retain the existing read-only carrier check.
    Editor slots are inspected in block order only until the first selected or
    active slot. No symbol/layer, current-glyph fallback or selection writer.
    """
    document = _document(deadline)
    if document.context[2] == "font":
        names = layers.names_font_window_selection(
            expected_fg_id=int(document.package.fgId), deadline=deadline
        )
        result = (
            _parent(document, document.package.findName(names[0]), 0, 0)
            if names
            else None
        )
        layers._check(deadline)
        return result
    for block in document.blocks:
        layers._check(deadline)
        for index in range(int(block.glyphsCount())):
            layers._check(deadline)
            info = block.getGlyphAt(index)
            if info is None or not (info.isSelected or info.isActive):
                continue
            result = _parent(document, info.glyph, int(block.id), index)
            layers._check(deadline)
            return result
    layers._check(deadline)
    return None
