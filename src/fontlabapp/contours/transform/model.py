# this_file: src/fontlabapp/contours/transform/model.py
# SPDX-License-Identifier: Apache-2.0
"""Shared transform writer and preview of Contours > Transform and Slant.

What: both scripts apply one affine matrix to the chosen layers.
``transform_changes`` plans one layer: one row for its shapes and one row
for its anchors. ``TransformEditor`` writes the plan; ``bakes`` decides per
shape how. ``layer_outline``, ``mapped``, ``outline_path`` and ``fit`` feed
the before/after preview. ``panel_type()`` returns ``TransformPanel``: the
``OutlinePanel`` of ``fontlabapp.contours.panel.model`` plus an outline preview of
the first glyph that may change.

How: every shape gets the composed transform (old shape transform, then the
matrix). A shape that ``bakes`` accepts then gets ``shape.applyTransform()``:
FontLab writes the new nodes and resets the matrix. This is FontLab's own
per-shape rule of the layer transform (``fllayer.cpp:6957-6978``): it bakes
only own contour shapes that only move, whose data no other shape shares
and that include no other shapes, and composes every other shape. The
write never calls ``layer.applyTransform``: the one-argument Python binding
also moves the guides, scales the advance and moves every anchor. Anchors
move in place, only when the user asks. An existing anchor that would land
on 0, 0 blocks Apply: ``anchor_writer.on_origin`` is the shared Redo rule
(FontLab issue 8527), here with a tolerance of ``ORIGIN_NEAR`` because
FontLab may round the stored point. The read-back accepts the same
tolerance for rounded nodes and anchors.

Why: Transform and Slant used private copies of this code. This module
imports only the standard library and stdlib-only App modules (``affine``,
``anchor_writer``, ``outline_writer``) at load time. PythonQt loads inside
the functions, and ``panel_type()`` loads the class from
``fontlabapp.contours.transform.ui``, so FontLab's 5-second cold import stays
fast. Offline tests do not prove native Undo/Redo.

How to use (a script)::

    import fly.ap.contours.transform.model as outline_transform

    class Slant(outline_transform.panel_type()):
        def preview_matrix(self, layer):
            return matrix, guide_y

        def planner(self):
            return lambda glyph, master, layer: outline_transform.transform_changes(
                layer, matrix, True, "250"
            )

        def editor(self):
            return outline_transform.TransformEditor()
"""

from typing import Any

import fontlabapp.contours.affine as affine  # noqa: PLR0402 - the package __getattr__ is native
import fontlabapp.anchors.writer as anchor_writer  # noqa: PLR0402 - the package __getattr__ is native
from fontlabapp import _native
from fontlabapp.contours.writer import (
    Change,
    Editor,
    Point,
    node_points,
    plural,
    translation,
)

#: A 2 x 3 affine matrix (m11, m12, m21, m22, dx, dy), as fontlabapp.contours.affine.
Affine = affine.Affine
#: A point (x, y) in font units.
XY = tuple[float, float]
#: Units. An anchor or a baked node this close to the plan counts as stored,
#: and an anchor this close to 0, 0 counts as on the origin.
ORIGIN_NEAR = 0.5
#: Preview margin in pixels.
FIT_MARGIN = 24


def bakes(shape: Any) -> bool:
    """True when FontLab's own layer transform writes the new nodes into the shape.

    FontLab's rule (``fllayer.cpp:6957-6978``): an own contour shape whose
    transform only moves, whose outline data no other shape shares and that
    includes no other shapes gets new node positions. Every other shape
    (components, shared data, scaled shapes) keeps its nodes and gets the
    composed shape transform. This function follows that rule and also
    composes a shape with no contours, which FontLab would bake. That is
    harmless: such a shape has no nodes to write.
    """
    return (
        not shape.isComponent
        and bool(shape.contours)
        # Raw count on purpose: FontLab bakes shared element data, component users included.
        and int(shape.shapeData.referenceCount) <= 1
        and translation(shape) is not None
        and not list(shape.includesList)
    )


def transform_changes(
    layer: Any, matrix: Affine, anchors: bool, note: str
) -> list[Change]:
    """Rows for one layer: the shapes, then the anchors when asked.

    Shape edit: ("shapes", [(shape, new shape transform, bakes, probe)]);
    `probe` is (first node, its expected glyph position) for a baked shape.
    Anchor edit: ("anchors", [(anchor, x, y)]). An anchor that would move
    onto 0, 0 blocks Apply: FontLab cannot redo that move (fl#8527). The
    rule is ``anchor_writer.on_origin``: the new point counts with the
    ``ORIGIN_NEAR`` rounding tolerance, the old point only when it is
    exactly 0, 0. So an anchor at (0.3, 0) that moves to (0, 0) is refused;
    only an anchor that is exactly on the origin already does not count.
    """
    if matrix == affine.IDENTITY:
        return []
    steps, nodes = [], 0
    for shape in layer.shapes:
        new = affine.concat(affine.from_qtransform(shape.transform), matrix)
        bake, probe = bakes(shape), None
        if not shape.isComponent:
            nodes += sum(int(contour.nodesCount) for contour in shape.contours)
        first = next((n for c in shape.contours for n in c.nodes()), None)
        if bake and first is not None:
            probe = (first, affine.apply(new, float(first.x), float(first.y)))
        steps.append((shape, new, bake, probe))
    rows = []
    if steps:
        rows.append(Change("outline", plural(nodes, "node"), note, ("shapes", steps)))
    moves, landed = [], []
    for pin in layer.anchors if anchors else ():
        old = (float(pin.point.x()), float(pin.point.y()))
        x, y = affine.apply(matrix, *old)
        moves.append((pin, x, y))
        near = anchor_writer.on_origin((x, y), ORIGIN_NEAR)
        if near and not anchor_writer.on_origin(old):
            landed.append(str(pin.name))
    if moves:
        problem = (
            f"{', '.join(landed)} would move to 0, 0; FontLab cannot redo that "
            "(fl#8527). Untick the anchors or change the values."
            if landed
            else ""
        )
        rows.append(
            Change(
                "anchors",
                plural(len(moves), "anchor"),
                "move",
                ("anchors", moves),
                problem,
            )
        )
    return rows


class TransformEditor(Editor):
    """Compose shape transforms, bake plain outlines, move anchors in place.

    Never a shape copy and never layer.applyTransform: FontLab's one-argument
    layer transform also moves guides, scales the advance and moves every
    anchor.
    """

    def write(self, layer: Any, steps: list[Any]) -> None:
        """Set each shape transform, bake the shapes that ``bakes`` accepts, move anchors."""
        qt = _native("PythonQt")
        for kind, items in steps:
            if kind == "anchors":
                for pin, x, y in items:
                    pin.point = qt.QtCore.QPointF(x, y)
                continue
            for shape, new, bake, _ in items:
                shape.transform = qt.QtGui.QTransform(*new)
                if bake:
                    shape.applyTransform()  # FontLab writes the nodes, resets the matrix
                shape.changed()

    def check(self, prepared: list[tuple[Any, list[Any]]]) -> list[str]:
        """Return "layer/anchor" or "layer: a shape" for each value FontLab did not keep."""
        missed: list[str] = []
        for layer, steps in prepared:
            for kind, items in steps:
                if kind == "anchors":
                    missed += [
                        f"{layer.name}/{pin.name}"
                        for pin, x, y in items
                        if abs(pin.point.x() - x) > ORIGIN_NEAR
                        or abs(pin.point.y() - y) > ORIGIN_NEAR
                    ]
                    continue
                for shape, new, bake, probe in items:
                    now = affine.from_qtransform(shape.transform)
                    want = affine.IDENTITY if bake else new
                    off = any(abs(a - b) > 1e-6 for a, b in zip(now, want, strict=True))
                    if bake and not off and probe is not None:  # FontLab may round
                        node, (x, y) = probe
                        off = (
                            abs(node.x - x) > ORIGIN_NEAR
                            or abs(node.y - y) > ORIGIN_NEAR
                        )
                    if off:
                        missed.append(f"{layer.name}: a shape")
        return missed


def layer_outline(layer: Any) -> list[list[Point]]:
    """Every contour of the layer as (x, y, on) lists, placed by its shape transform."""
    result = []
    for shape in layer.shapes:
        matrix = affine.from_qtransform(shape.transform)
        for contour in shape.contours:
            result.append(
                [(*affine.apply(matrix, x, y), on) for x, y, on in node_points(contour)]
            )
    return result


def mapped(contours: list[list[Point]], matrix: Affine) -> list[list[Point]]:
    """The same contours after `matrix`."""
    return [[(*affine.apply(matrix, x, y), on) for x, y, on in c] for c in contours]


def outline_path(contours: list[list[Point]]) -> Any:
    """QPainterPath of closed contours: cubic for two controls, quadratic for one."""
    from fontlab_pens.qt import QPainterPathPen, draw_onoff_contours

    pen = QPainterPathPen(path=_native("PythonQt").QtGui.QPainterPath())
    # Contours with no on-curve point stay undrawn (pens would draw a TrueType loop).
    draw_onoff_contours([c for c in contours if any(p[2] for p in c)], pen)
    return pen.path


def fit(box: Any, width: float, height: float) -> Affine:
    """Map font units in `box` (y up) into a width × height widget (y down)."""
    if box.width() <= 0 or box.height() <= 0:
        return affine.IDENTITY
    scale = min(
        (width - 2 * FIT_MARGIN) / box.width(), (height - 2 * FIT_MARGIN) / box.height()
    )
    if scale <= 0:
        return affine.IDENTITY
    dx = (width - box.width() * scale) / 2 - box.x() * scale
    dy = (height + box.height() * scale) / 2 + box.y() * scale
    return (scale, 0.0, 0.0, -scale, dx, dy)


def panel_type() -> type:
    """Return the ``TransformPanel`` base class (a PythonQt ``QDialog``).

    It is ``OutlinePanel`` (``fontlabapp.contours.panel.model.panel_type()``) with
    an ``OutlinePreview`` below the form. The class loads PythonQt, so call
    this inside FontLab only. Subclass it like ``OutlinePanel`` and add the
    hook ``preview_matrix(layer)`` that returns (matrix, guide y or None).
    See ``fontlabapp.contours.transform.ui.TransformPanel``.
    """
    from fontlabapp.contours.transform.ui import TransformPanel

    return TransformPanel


__all__ = [
    "FIT_MARGIN",
    "ORIGIN_NEAR",
    "XY",
    "Affine",
    "TransformEditor",
    "bakes",
    "fit",
    "layer_outline",
    "mapped",
    "outline_path",
    "panel_type",
    "transform_changes",
]
