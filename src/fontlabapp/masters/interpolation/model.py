# this_file: src/fontlabapp/masters/interpolation/model.py
# SPDX-License-Identifier: Apache-2.0
"""Original all-node interpolation and complete painter paths, loaded without Qt.

Keep the L1 preview's contour order, transformed components, node-kind checks,
endpoint blending and quadratic/cubic closure. Native Qt loads only when needed.
The menu and shared painter use these helpers; no font geometry is written.
"""

from typing import Any

from fontlabapp import _native
from fontlabapp.components.inspect.model import selected_names as _selected_names
from fontlabapp.masters.inspect.model import muted  # noqa: F401 - Original public helper re-export.

Points = list[tuple[float, float, bool]]
Outlines = list[Points]


def selected_names() -> list[str]:
    """Retain Font-window order, otherwise the current glyph even when it is falsey."""
    try:
        names = _selected_names()
    except Exception:  # noqa: BLE001 - Preserve the original Font-window fallback.
        names = []
    if names:
        return names
    glyph = _native("fontlab").CurrentGlyph()
    return [glyph.name] if glyph is not None else []


def master_layers(glyph: Any, masters: list[str]) -> dict[str, Any]:
    """{master: flLayer} for the masters present in this glyph."""
    found = {}
    for master in masters:
        layer = glyph.findLayer(master)
        if layer is not None and (not layer.isNull):
            found[master] = layer
    return found


def node_points(contour: Any) -> Points:
    """Read every original node coordinate and on-curve flag in contour order."""
    return [(node.x, node.y, bool(node.isOn())) for node in contour.nodes()]


def outline(layer: Any) -> Outlines:
    """Own contours plus component contours placed by their transforms, as [(x, y, on)] lists."""
    result = []
    for shape in layer.shapes:
        transform = shape.transform
        for contour in shape.contours:
            points = node_points(contour)
            if not transform.isIdentity():
                QtCore = _native("PythonQt").QtCore
                points = [
                    (p.x(), p.y(), on)
                    for x, y, on in points
                    for p in [transform.map(QtCore.QPointF(x, y))]
                ]
            result.append(points)
    return result


def problem(a: Outlines, b: Outlines) -> str | None:
    """Why outlines a and b cannot interpolate, or None."""
    if len(a) != len(b):
        return f"{len(a)} vs {len(b)} contours"
    for i, (ca, cb) in enumerate(zip(a, b, strict=False), start=1):
        if [p[2] for p in ca] != [p[2] for p in cb]:
            return f"contour {i}: {len(ca)} vs {len(cb)} nodes or different node types"
    return None


def blend(a: Outlines, b: Outlines, t: float) -> Outlines:
    """Blend each corresponding node without rounding or changing input outlines."""
    return [
        [
            (pa[0] + (pb[0] - pa[0]) * t, pa[1] + (pb[1] - pa[1]) * t, pa[2])
            for pa, pb in zip(ca, cb, strict=False)
        ]
        for ca, cb in zip(a, b, strict=False)
    ]


def outline_path(contours: Outlines) -> Any:
    """QPainterPath from contours given as [(x, y, on)] lists (cubic for two handles)."""
    from fontlab_pens.qt import QPainterPathPen, draw_onoff_contours

    pen = QPainterPathPen(path=_native("PythonQt").QtGui.QPainterPath())
    # Contours with no on-curve point stay undrawn (pens would draw a TrueType loop).
    draw_onoff_contours([c for c in contours if any(p[2] for p in c)], pen)
    return pen.path


def fit_transform(rect: Any, width: float, height: float, margin: float = 16) -> Any:
    """QTransform mapping font units in rect (y up) into a width × height widget (y down)."""
    QtGui = _native("PythonQt").QtGui
    if rect.width() <= 0 or rect.height() <= 0:
        return QtGui.QTransform()
    scale = min(
        (width - 2 * margin) / rect.width(), (height - 2 * margin) / rect.height()
    )
    if scale <= 0:
        return QtGui.QTransform()
    dx = (width - rect.width() * scale) / 2 - rect.x() * scale
    dy = (height + rect.height() * scale) / 2 + rect.y() * scale
    return QtGui.QTransform(scale, 0, 0, -scale, dx, dy)
