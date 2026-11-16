# this_file: tests/_tmetrics_fakes.py
# SPDX-License-Identifier: Apache-2.0
"""A borrowed font with Fontport-shaped ``edit_glyph`` for the TMetrics write tests.

``edit_glyph`` stages a detached fontParts glyph, writes it back once on a clean
exit and records ``(name, layer, undo_name)``; ``fail`` makes the write raise.
"""

from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

import _cov_qt as fq


class EditableFont(fq.FontModel):
    """``fq.FontModel`` plus ``edit_glyph`` and ``defaultLayerName``."""

    defaultLayerName = "public.default"

    def __init__(self, ufo: Any = None, editable: bool = True) -> None:
        super().__init__(fq.ufo_font() if ufo is None else ufo, editable)
        self.features = SimpleNamespace(text="")
        self.edits: list[tuple[str, Any, str]] = []
        self.fail: Exception | None = None

    @contextmanager
    def edit_glyph(self, name: str, *, layer: Any = None, undo_name: str):
        from fontParts.fontshell import RGlyph

        source = self.ufo[name]
        staged = RGlyph()
        staged.width = source.width
        source.drawPoints(staged.getPointPen())
        for anchor in source.anchors:
            staged.appendAnchor(anchor.name, (anchor.x, anchor.y))
        yield staged
        if self.fail is not None:
            raise self.fail
        source.clearContours()
        source.clearComponents()
        source.anchors.clear()
        staged.drawPoints(source.getPointPen())
        source.width = staged.width
        for anchor in staged.anchors:
            source.appendAnchor({"name": anchor.name, "x": anchor.x, "y": anchor.y})
        self.edits.append((name, layer, undo_name))


def composite_font() -> EditableFont:
    """``EditableFont`` with an anchor on A and a composite B (component A at x=0)."""
    font = EditableFont()
    font.ufo["A"].appendAnchor({"name": "top", "x": 300, "y": 700})
    glyph = font.ufo.newGlyph("B")
    glyph.width = 600
    glyph.unicodes = [66]
    glyph.getPointPen().addComponent("A", (1, 0, 0, 1, 0, 0))
    return font


class TwoLayerFont(EditableFont):
    """``EditableFont`` whose ufoLib2 font also has a ``Bold`` layer: A 700 wide, bounds 50..650.

    ``getLayer`` returns the real ufoLib2 layer, so reads follow it; ``edit_glyph``
    with ``layer="Bold"`` writes that layer's glyph.
    """

    def __init__(self) -> None:
        super().__init__()
        bold = self.ufo.newLayer("Bold")
        for name, width, points in (
            ("A", 700, ((50, 0), (350, 700), (650, 0))),
            ("V", 600, ((0, 700), (300, 0), (600, 700))),
        ):
            glyph = bold.newGlyph(name)
            glyph.width = width
            pen = glyph.getPen()
            pen.moveTo(points[0])
            for point in points[1:]:
                pen.lineTo(point)
            pen.closePath()

    def getLayer(self, name: str) -> Any:
        if name == self.defaultLayerName:
            return self.ufo.layers.defaultLayer
        return self.ufo.layers[name]

    @contextmanager
    def edit_glyph(self, name: str, *, layer: Any = None, undo_name: str):
        if layer in (None, self.defaultLayerName):
            with super().edit_glyph(name, layer=layer, undo_name=undo_name) as glyph:
                yield glyph
            return
        target = self.ufo.layers[layer][name]
        staged = SimpleNamespace(width=target.width)
        yield staged
        if self.fail is not None:
            raise self.fail
        target.width = staged.width
        self.edits.append((name, layer, undo_name))
