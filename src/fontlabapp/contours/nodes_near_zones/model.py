# this_file: src/fontlabapp/contours/nodes_near_zones/model.py
# SPDX-License-Identifier: Apache-2.0
"""Nodes Near Zones: on-curve nodes just off a vertical metric line.

``scan`` reads the named glyphs on every master and lists each on-curve node
whose height is within ``tolerance`` units of, but not on, baseline, x-height,
cap height, ascender or descender. Nothing is written.
"""

from dataclasses import dataclass
from typing import Any

HEADER = "Glyph\tMaster\tZone\tZone y\tNode x\tNode y\tOff by"
DEFAULT_TOLERANCE = 4


@dataclass(frozen=True)
class NodesNearZonesReport:
    """One scan: package it was read from, glyph and master counts, tolerance, rows."""

    package_id: int
    glyphs: int
    masters: int
    tolerance: int
    rows: tuple


def zones(metrics: Any) -> tuple:
    """Named vertical zones for one master's metrics."""
    return (("baseline", 0.0), ("x-height", metrics.xHeight), ("cap height", metrics.capsHeight),
            ("ascender", metrics.ascender), ("descender", metrics.descender))


def on_curve_points(layer: Any, point_type: Any) -> list:
    """On-curve node positions of the layer's own shapes; ``point_type`` is QPointF."""
    points = []
    for shape in layer.shapes:
        if shape.shapeData is not None and shape.shapeData.componentGlyph:
            continue
        for contour in shape.getContours():
            for node in contour.nodes():
                if node.isOn():
                    point = shape.transform.map(point_type(node.x, node.y))
                    points.append((point.x(), point.y()))
    return points


def near_misses(points: list, zone_list: tuple, tolerance: float) -> list:
    """``(label, zone y, x, y)`` where ``0 < |y - zone y| <= tolerance``."""
    return [(label, value, x, y) for x, y in points for label, value in zone_list
            if 0 < abs(y - value) <= tolerance]


def scan(package: Any, names: list, tolerance: float, metrics_of: Any, point_type: Any) -> tuple:
    """Rows ``(glyph, master, zone, zone y, x, y)``; ``metrics_of(master)`` gives metrics."""
    rows = []
    cache: dict = {}
    for name in names:
        glyph = package.findName(name)
        if glyph is None:
            continue
        for master in package.masters:
            layer = glyph.findLayer(master)
            if layer is None:
                continue
            if master not in cache:
                cache[master] = zones(metrics_of(master))
            found = near_misses(on_curve_points(layer, point_type), cache[master], tolerance)
            rows += [(name, master, label, value, x, y) for label, value, x, y in found]
    return tuple(rows)


def render(report: NodesNearZonesReport) -> str:
    """Tab-separated table with the signed offset of each node."""
    lines = [HEADER]
    lines += [f"{g}\t{m}\t{z}\t{v:g}\t{x:g}\t{y:g}\t{y - v:+g}" for g, m, z, v, x, y in report.rows]
    return "\n".join(lines)


def summary(report: NodesNearZonesReport) -> str:
    """One-line result for the status bar."""
    scope = f"{report.glyphs} glyph{'s' if report.glyphs != 1 else ''} x {report.masters} masters"
    if not report.rows:
        return f"No nodes within {report.tolerance} units of a zone ({scope})."
    count, glyphs = len(report.rows), len({row[0] for row in report.rows})
    return (f"{count} near miss{'es' if count != 1 else ''} in {glyphs} glyph{'s' if glyphs != 1 else ''}"
            f" within {report.tolerance} units ({scope}).")
