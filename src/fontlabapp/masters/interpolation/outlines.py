# this_file: src/fontlabapp/masters/interpolation/outlines.py
"""Read a glyph's master layers and their compatibility with the shown layer.

Evidence classes follow Issue 209 ``native-data-map.md`` §1: ``package.masters``
(a-stub) and ``glyph.findLayer`` through ``model.master_layers`` (a-stub, b).
Compatibility is computed in Python by ``model.problem`` (contour count, node
count per contour and on/off-curve pattern); ``layer.isCompatible`` and
``interpolateInstance`` are never called. Used by
``fontlabapp.plugins.snapshot.capture``.
"""

from collections.abc import Callable
from typing import Any

__all__ = ["read"]

Row = tuple[str, tuple[Any, ...], tuple[Any, ...], float, bool]


def _points(contours: tuple[Any, ...]) -> list[list[tuple[float, float, bool]]]:
    """Contour records as ``model.problem``'s ``[(x, y, on)]`` lists."""
    return [[(n.x, n.y, n.on_curve) for n in c.nodes] for c in contours]


def read(
    package: Any,
    glyph: Any,
    shown: tuple[Any, ...],
    contours: Callable[[Any], tuple[Any, ...]],
    anchors: Callable[[Any], tuple[Any, ...]],
    *,
    items: Callable[[Callable[[], Any]], list[Any]],
) -> tuple[Row, ...]:
    """Return ``(name, contours, anchors, advance, compatible)`` per master.

    Every name in ``package.masters`` with a layer is listed in package order,
    including the shown layer's master. ``shown`` holds the displayed layer's
    own contours; ``contours`` and ``anchors`` read one layer the same way.
    ``compatible`` therefore ignores components and the open/closed state.
    """
    from fontlabapp.masters.interpolation.model import master_layers, problem

    names = [str(name) for name in items(lambda: package.masters)]
    reference = _points(shown)
    rows = []
    for name, layer in master_layers(glyph, names).items():
        shapes = contours(layer)
        compatible = problem(reference, _points(shapes)) is None
        rows.append(
            (name, shapes, anchors(layer), float(layer.advanceWidth), compatible)
        )
    return tuple(rows)
