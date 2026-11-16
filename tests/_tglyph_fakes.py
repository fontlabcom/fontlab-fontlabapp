# this_file: tests/_tglyph_fakes.py
# SPDX-License-Identifier: Apache-2.0
"""Layered fontParts fonts for the TGlyph model and window tests.

``layered_font()`` is a fontshell RFont with ``public.default`` and ``Bold``:
``a`` is a closed cubic contour plus an open line, a quadratic run and an
anchor; ``b`` is a composite of ``a``; ``hole`` refers to a missing base; ``Bold`` carries a wider ``a`` only.
``editable_font()`` is the same font with a layered ``edit_glyph`` fake, and
``unsupported_layer()`` a layer whose ``layer[name]`` raises like Fontport's
``UnsupportedCapability``.
"""

from contextlib import contextmanager

from fontParts.fontshell import RFont, RGlyph


def _draw_a(glyph, shift: float = 0.0) -> None:
    pen = glyph.getPointPen()
    pen.beginPath()
    pen.addPoint((0 + shift, 0), "line")
    pen.addPoint((100 + shift, 0), "line", smooth=True)
    pen.addPoint((150 + shift, 50))
    pen.addPoint((150 + shift, 150))
    pen.addPoint((100 + shift, 200), "curve", smooth=True)
    pen.addPoint((0 + shift, 200), "line")
    pen.endPath()
    pen.beginPath()
    pen.addPoint((10, 300), "move")
    pen.addPoint((90, 300), "line")
    pen.endPath()
    pen.beginPath()
    pen.addPoint((200, 0), "qcurve")
    pen.addPoint((250, 50))
    pen.addPoint((250, 100))
    pen.addPoint((200, 150), "qcurve")
    pen.addPoint((180, 75))
    pen.endPath()


class EditableFont(RFont):
    """fontshell RFont with Fontport's ``edit_glyph`` contract on any layer.

    The staged copy holds width, contours, components and anchors; the
    source layer's glyph is replaced only when the block exits cleanly and
    ``fail`` is None. Each write is logged as ``(name, layer, undo_name)``.
    """

    edits: list
    fail: Exception | None = None

    @contextmanager
    def edit_glyph(self, name, *, layer=None, undo_name="FontParts glyph edit"):
        layer = layer or self.defaultLayerName
        source = self.getLayer(layer)[name]
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
        source.clearAnchors()
        source.width = staged.width
        staged.drawPoints(source.getPointPen())
        for anchor in staged.anchors:
            source.appendAnchor(anchor.name, (anchor.x, anchor.y))
        self.edits.append((name, layer, undo_name))


def editable_font() -> EditableFont:
    font = layered_font(EditableFont)
    font.edits = []
    return font


def layered_font(cls: type = RFont) -> RFont:
    font = cls()
    font.info.unitsPerEm = 1000
    font.info.ascender = 750
    font.info.descender = -250
    font.info.xHeight = 500
    font.info.capHeight = 700
    a = font.newGlyph("a")
    a.width = 500
    _draw_a(a)
    a.appendAnchor("top", (250, 600))
    b = font.newGlyph("b")
    b.width = 500
    b.getPointPen().addComponent("a", (1, 0, 0, 1, 10, 20))
    hole = font.newGlyph("hole")
    hole.getPointPen().addComponent("missing", (1, 0, 0, 1, 0, 0))
    font.newGlyph("space").width = 250
    bold = font.newLayer("Bold")
    wide = bold.newGlyph("a")
    wide.width = 700
    _draw_a(wide, 20.0)
    return font


class _Glyph:
    """A glyph that only draws components (defcon refuses self-references)."""

    def __init__(self, *components: tuple[str, tuple]) -> None:
        self.components, self.width, self.anchors = components, 0, ()

    def drawPoints(self, pen) -> None:
        for base, matrix in self.components:
            pen.addComponent(base, matrix)


def cyclic_font() -> dict:
    """A plain mapping layer where ``loop`` uses ``knot`` which uses ``loop``."""
    identity = (1, 0, 0, 1, 0, 0)
    return {"loop": _Glyph(("knot", identity)), "knot": _Glyph(("loop", identity))}


class _Unsupported(dict):
    """A plain layer whose ``layer[name]`` raises NotImplementedError for ``raising`` names."""

    def __init__(self, glyphs: dict, raising: set) -> None:
        super().__init__(glyphs)
        self.raising = raising
        self.info = None

    def __getitem__(self, name):
        if name in self.raising:
            raise NotImplementedError(f"components.unresolvedBase: Cyclic component dependency: {name}")
        return super().__getitem__(name)

    @contextmanager
    def edit_glyph(self, name, *, layer=None, undo_name="FontParts glyph edit"):
        """Like Fontport ``RFont.edit_glyph``: stage the raw glyph without resolving components."""
        source = dict.__getitem__(self, name)
        staged = RGlyph()
        staged.width = source.width
        source.drawPoints(staged.getPointPen())
        yield staged
        source.clearContours()
        for contour in staged.contours:
            source.appendContour(contour)
        self.edits.append((name, layer, undo_name))


def unsupported_layer(owner_raises: bool = False, editable: bool = True) -> _Unsupported:
    """``own`` has a triangle and a component of ``knot``; ``knot`` (or ``own``) raises."""
    own = RGlyph()
    own.width = 300
    pen = own.getPointPen()
    pen.beginPath()
    for point in ((0, 0), (100, 0), (50, 100)):
        pen.addPoint(point, "line")
    pen.endPath()
    pen.addComponent("knot", (1, 0, 0, 1, 0, 0))
    raising = {"own", "knot"} if owner_raises else {"knot"}
    layer = _Unsupported({"own": own, "knot": RGlyph()}, raising)
    layer.edits = []
    if not editable:
        layer.edit_glyph = None
    return layer
