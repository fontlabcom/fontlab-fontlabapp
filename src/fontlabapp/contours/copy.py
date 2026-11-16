# this_file: src/fontlabapp/contours/copy.py
# SPDX-License-Identifier: Apache-2.0
"""Contour copies and Qt path contours of the Contours generator scripts.

What: Shadow Copy, Small Caps From Capitals, Superior & Inferior Figures and
Tabular Figure Copies copy the contours of a layer through a transform;
Outline Effect turns a stroked ``QPainterPath`` back into FontLab contours.
This module holds those shared parts:

- ``contour_shapes`` gives the own (non-component) shapes that hold contours.
- ``copy_contours`` copies their contours: first the element transform,
  then the caller's transform. ``repair_nodes`` copies the node names and
  raw node flags back onto each copy.
- ``path_contours`` builds closed ``flContour`` objects from the elements
  of a ``QPainterPath``.

How: a contour copy is ``contour.cloneMapped(...)``. FontLab's contour copy
can drop node names and raw node flags (fl#8569). ``repair_nodes`` copies
only these two fields back: the node names and raw node flags. Other node
properties, contour names and element names and notes are not copied by
``copy_contours``. ``restore_shape`` repairs a whole detached shape, including
its shape-data name/note and contour names. It keeps clone selection bits
by default; ``keep_view_state=True`` restores source selection and active flags.

Why: the code was a private copy in five scripts. ``contour_shapes`` is not
``fontlabapp.contours.writer.outline_shapes``: that one returns the shapes
that an outline script may edit in place, and it keeps shared and scaled
shapes out. A copy can use those shapes too, because it maps every contour
through its element transform.

This module imports only the standard library at load time. ``path_contours``
loads ``fontlab`` and PythonQt when it runs, so FontLab's 5-second cold
import stays fast. Offline tests do not prove native FontLab behaviour.

How to use (a script)::

    import fly.ap.contours.copy as contour_copy

    copies = contour_copy.copy_contours(layer, move)  # read before history
"""

from collections.abc import Sequence
from typing import Any

from fontlabapp import _native

#: Node state bit "selected". A copy clears it: new outlines must not look selected.
SELECTED = 0x0020
#: QPainterPath element types; CurveTo is 2 and its two data points are 3.
MOVE_TO, LINE_TO = 0, 1


def contour_shapes(layer: Any) -> list[Any]:
    """Return the non-component shapes of ``layer`` that hold contours, in layer order."""
    return [s for s in layer.shapes if not s.isComponent and len(s.contours)]


def repair_nodes(source: Any, copy: Any) -> None:
    """Copy the node names and raw node flags of ``source`` onto its copy.

    A FontLab contour copy can drop node names and raw node flags (fl#8569).
    Only these two fields are copied back (``name`` and ``nodeState``); the
    selection bit is cleared. A copy with another node count raises
    ``RuntimeError``: the nodes cannot be paired.
    """
    before, after = source.nodes(), copy.nodes()
    if len(before) != len(after):
        raise RuntimeError("FontLab changed the node count of a contour copy.")
    for old, new in zip(before, after, strict=True):
        new.name = old.name
        new.nodeState = old.nodeState & ~SELECTED


def restore_shape(
    source: Any,
    clone: Any,
    keep_view_state: bool = False,
    indexes: Sequence[int] | None = None,
) -> None:
    """Restore fields that FontLab can drop from a detached shape clone.

    Call after cloning and before adding the clone to a layer. Copy the
    shape-data note/name, contour names, node names and raw connection flags.
    By default keep clone node selection bits and shape view state. With
    ``keep_view_state=True``, copy full source nodeState and shape active and
    selected flags. Pass ``indexes`` to pair a subset of source contours
    with clone contours, in that order; None pairs all source contours.
    Example: ``restore_shape(source, clone, True, indexes=[2, 0])``.
    Use only a detached clone; mismatched counts raise RuntimeError to avoid
    storing flags on the wrong nodes.
    """
    before, after = list(source.contours), list(clone.contours)
    if indexes is not None:
        before = [before[index] for index in indexes]
    if len(before) != len(after):
        raise RuntimeError("FontLab changed the contour count of a shape copy.")
    clone.shapeData.note = source.shapeData.note
    clone.shapeData.name = source.shapeData.name
    if keep_view_state:
        clone.active, clone.selected = source.active, source.selected
    for old, new in zip(before, after, strict=True):
        states = [node.nodeState for node in old.nodes()] if keep_view_state else [
            node.nodeState & SELECTED for node in new.nodes()
        ]
        repair_nodes(old, new)
        for node, state in zip(new.nodes(), states, strict=True):
            node.nodeState = state if keep_view_state else node.nodeState | state
        new.name = old.name


def copy_contours(layer: Any, transform: Any) -> list[Any]:
    """Return repaired copies of the layer contours: element transform, then ``transform``.

    ``transform`` is a ``QTransform``. Call this before history starts: it
    only reads the layer, so a failed copy changes nothing.
    """
    copies = []
    for shape in contour_shapes(layer):
        for contour in shape.contours:
            copy = contour.cloneMapped(shape.transform).cloneMapped(transform)
            repair_nodes(contour, copy)
            copies.append(copy)
    return copies


def path_contours(path: Any) -> list[Any]:
    """Return closed flContours from the elements of a QPainterPath.

    MoveTo starts a contour, LineTo adds an on-curve node, CurveTo adds two
    cubic handles ("curve" nodes) and the end point. A closing point that
    repeats the start replaces the start node. Pieces with fewer than three
    nodes are dropped (the Qt stroker can leave such stubs).
    """
    fontlab, point = _native("fontlab"), _native("PythonQt").QtCore.QPointF
    groups: list[list[Any]] = []
    nodes: list[Any] = []
    index = 0
    while index < path.elementCount():
        element = path.elementAt(index)
        kind = int(element.type)
        if kind in (MOVE_TO, LINE_TO):
            if kind == MOVE_TO and nodes:
                groups.append(nodes)
                nodes = []
            nodes.append(fontlab.flNode(point(element.x, element.y), nodeType="on"))
            index += 1
            continue
        second, end = path.elementAt(index + 1), path.elementAt(index + 2)
        nodes.append(fontlab.flNode(point(element.x, element.y), nodeType="curve"))
        nodes.append(fontlab.flNode(point(second.x, second.y), nodeType="curve"))
        nodes.append(fontlab.flNode(point(end.x, end.y), nodeType="on"))
        index += 3
    if nodes:
        groups.append(nodes)
    contours = []
    for group in groups:
        first, last = group[0], group[-1]
        if len(group) > 1 and (first.x, first.y) == (last.x, last.y):
            group[0] = group.pop()
        if len(group) > 2:
            contours.append(fontlab.flContour(group, closed=True))
    return contours


__all__ = [
    "LINE_TO",
    "MOVE_TO",
    "SELECTED",
    "contour_shapes",
    "copy_contours",
    "path_contours",
    "repair_nodes",
    "restore_shape",
]
