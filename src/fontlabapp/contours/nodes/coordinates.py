# this_file: src/fontlabapp/contours/nodes/coordinates.py
# SPDX-License-Identifier: Apache-2.0
"""Read own selected nodes and measure consecutive pairs without native writes.

Keep the original L1 node order, offsets, distances, angles and rounding. Import
without FontLab or Qt; resolve the active glyph only when a panel requests it.
"""

import itertools
import math
from typing import Any

from fontlabapp import _native

NodeRow = tuple[int, int, float, float, bool]


def current_glyph(package: Any) -> Any | None:
    """Resolve actual active context; a valid FontGate glyph can evaluate false.

    flWorkspace.currentGlyph is a cache. CurrentGlyph uses the active Font/Glyph
    window. Resolve only its name through the panel's already checked package.
    """
    glyph = _native("fontlab").CurrentGlyph()
    return package.findName(glyph.name) if glyph is not None else None


def own_contours(layer: Any) -> list[Any]:
    """Keep drawn contours only; exclude all contours reached through components."""
    return [
        contour
        for shape in layer.shapes
        if not shape.isComponent
        for contour in shape.contours
    ]


def selected_nodes(layer: Any) -> list[NodeRow]:
    """Return own-contour/node indices, raw coordinates and on-curve flags."""
    rows = []
    for c, contour in enumerate(own_contours(layer)):
        for n, node in enumerate(contour.nodes()):
            if node.selected:
                rows.append((c, n, node.x, node.y, bool(node.isOn())))
    return rows


def measures(rows: list[NodeRow]) -> list[tuple[str, float, float, float, float]]:
    """Measure each consecutive selected pair, retaining degrees and direction."""
    result = []
    for a, b in itertools.pairwise(rows):
        dx, dy = b[2] - a[2], b[3] - a[3]
        result.append(
            (
                f"{a[0] + 1}:{a[1]} → {b[0] + 1}:{b[1]}",
                dx,
                dy,
                math.hypot(dx, dy),
                math.degrees(math.atan2(dy, dx)),
            ),
        )
    return result


def number(value: float) -> str:
    """Use original one-decimal coordinate display, with redundant zeros removed."""
    return (
        f"{value:.1f}".rstrip("0").rstrip(".")
        if value != int(value)
        else str(int(value))
    )
