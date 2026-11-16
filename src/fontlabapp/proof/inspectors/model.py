# this_file: src/fontlabapp/proof/inspectors/model.py
# SPDX-License-Identifier: Apache-2.0
"""Read-only metrics and raw contour inspectors adapted from fontlab-samples.

Keep missing/auto and winding semantics exact. Native APIs load lazily; reads
never touch flGlyph.fgGlyph or notify font/history changes.
"""

import itertools
from typing import Any

from fontlabapp.masters.inspect.model import (
    all_names as _all_names,
    layer_contours,
    master_layers,
    node_points,
    own_contours,
    muted as muted,
)  # noqa: PLC0414 - original public helper
from fontlabapp.masters.inspect.model import selected_names as selected_names
from fontlabapp.proof.inspect.model import (
    layer_path,
    selected_glyphs as selected_glyphs,
)


def all_names(package: Any = None) -> list[str]:
    """Keep the original package argument while sharing ordered Font-window reads."""
    return _all_names()


def outline(layer: Any) -> Any:
    """Reuse actual transformed closed/open outlines, including component geometry."""
    return layer_path(layer)


def parse_text(text: Any, package: Any) -> Any:
    """Glyph names for the text: characters by Unicode, '/name' tokens by name (ended by space or '/')."""
    names, i = [], 0
    while i < len(text):
        char = text[i]
        if char == "/":
            j = i + 1
            while j < len(text) and text[j] not in " /":
                j += 1
            token = text[i + 1 : j]
            if token and package.findName(token) is not None:
                names.append(token)
            i = j + (1 if j < len(text) and text[j] == " " else 0)
            continue
        glyph = package.findUnicode(ord(char))
        if glyph is not None:
            names.append(glyph.name)
        i += 1
    return names


def layout(package: Any, names: Any, master: Any) -> Any:
    """[(name, x, advance, lsb, rsb)]: pen positions along the line, in font units."""
    rows, x = [], 0
    for name in names:
        layer = package.findName(name).findLayer(master)
        if layer is None or layer.isNull:
            continue
        advance = layer.advanceWidth
        box = layer.boundingBox
        empty = box.width() <= 0 and box.height() <= 0
        lsb = None if empty else box.x()
        rsb = None if empty else advance - box.x() - box.width()
        rows.append((name, x, advance, lsb, rsb))
        x += advance
    return rows


def widths(glyph: Any, masters: Any) -> Any:
    """[width or None] in master order."""
    out = []
    for master in masters:
        layer = glyph.findLayer(master)
        out.append(None if layer is None or layer.isNull else round(layer.advanceWidth))
    return out


def progression(values: Any) -> str:
    """'rising', 'falling', 'flat' or 'mixed' for a list of widths (None ignored)."""
    known = [v for v in values if v is not None]
    steps = [b - a for a, b in itertools.pairwise(known)]
    if all(s == 0 for s in steps):
        return "flat"
    if all(s >= 0 for s in steps):
        return "rising"
    if all(s <= 0 for s in steps):
        return "falling"
    return "mixed"


def report(glyphs: Any, masters: Any) -> Any:
    """[(name, [widths], progression)] for the glyphs, in the given order."""
    rows = []
    for glyph in glyphs:
        values = widths(glyph, masters)
        rows.append((glyph.name, values, progression(values)))
    return rows


def signed_area(points: Any) -> Any:
    """Return the signed area of the raw node polygon, including controls."""
    return (
        sum(
            a[0] * b[1] - b[0] * a[1]
            for a, b in zip(points, points[1:] + points[:1], strict=False)
        )
        / 2.0
    )


def contour_info(layer: Any) -> Any:
    """[(index, points, start (x, y), next point (x, y), 'ccw'|'cw')] for the layer's own contours."""
    info = []
    for index, contour in enumerate(own_contours(layer)):
        points = node_points(contour)
        if not points:
            continue
        direction = "ccw" if signed_area([p[:2] for p in points]) > 0 else "cw"
        info.append(
            (index, points, points[0][:2], points[1 % len(points)][:2], direction),
        )
    return info


def layer_counts(layer: Any) -> Any:
    """(contours, nodes) drawn in the layer, or None for an auto layer."""
    if layer.autoLayer:
        return None
    contours = own_contours(layer)
    return len(contours), sum(contour.nodesCount for contour in contours)


def glyph_counts(glyph: Any, masters: Any) -> Any:
    """Read present masters only; preserve None for automatic layers."""
    return {
        master: layer_counts(layer)
        for master, layer in master_layers(glyph, masters).items()
    }


def incompatible(counts: Any) -> Any:
    """Flag differing real contour/node counts, ignoring auto and missing layers."""
    values = {value for value in counts.values() if value is not None}
    return len(values) > 1


def outline_source(layer: Any) -> tuple:
    """Snapshot transformed raw nodes and closure, without native wrapper equality.

    Shared Masters geometry reads include transformed components. Plain values
    keep repaint source checks independent of PythonQt value-object identity.
    """
    closed = [
        bool(contour.closed) for shape in layer.shapes for contour in shape.contours
    ]
    return tuple(
        (flag, tuple(points))
        for flag, points in zip(closed, layer_contours(layer), strict=True)
    )
