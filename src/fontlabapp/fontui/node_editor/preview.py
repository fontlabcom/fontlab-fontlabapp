# this_file: src/fontlabapp/fontui/node_editor/preview.py
# SPDX-License-Identifier: Apache-2.0
"""Detached coincident-node overlays over the captured TGlyph drawing."""

from dataclasses import replace

from fontlabapp.fontui.tglyph_model import Contour, Point


def literal(data, before, result, layer_id):
    """Preserve displayed shape transforms while adding planned coincident points."""
    source = next(row for row in before.source.layers if row.key == layer_id)
    target = next(row for row in result.layers if row.key == layer_id)
    if data is None or len(data.contours) != len(source.paths):
        raise ValueError("TGlyph cannot display the captured node topology.")
    contours = []
    for drawing, old, new in zip(data.contours, source.paths, target.paths, strict=True):
        if len(drawing.points) != len(old.nodes):
            raise ValueError("TGlyph node order differs from the captured source.")
        positions = {(node.x, node.y): point for node, point in zip(old.nodes, drawing.points, strict=True)}
        points = []
        for index, node in enumerate(new.nodes):
            shown = positions[(node.x, node.y)]
            kind = None if node.kind == "off" else node.kind
            if index == 0 and not new.closed:
                kind = "move"
            points.append(Point(shown.x, shown.y, kind, bool(node.flags & 8)))
        contours.append(Contour(tuple(points)))
    return replace(data, contours=tuple(contours))


def per_glyph(data, layer, edits):
    """Apply the per-glyph indices to detached points, leaving all live nodes alone."""
    native = [contour for shape in layer.shapes if not shape.isComponent for contour in shape.contours]
    if data is None or len(native) != len(data.contours):
        raise ValueError("TGlyph cannot display the captured node topology.")
    contours = list(data.contours)
    for contour, indices, handles in edits:
        index = next(i for i, value in enumerate(native) if value is contour)
        points = list(contours[index].points)
        for node in reversed(indices):
            point = points[node]
            fresh = [Point(point.x, point.y, None), Point(point.x, point.y, None)] if handles else []
            fresh.append(Point(point.x, point.y, "curve" if handles else "line"))
            points[node + 1:node + 1] = fresh
        contours[index] = Contour(tuple(points))
    return replace(data, contours=tuple(contours))
