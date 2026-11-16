# this_file: src/fontlabapp/components/inspect/model.py
# SPDX-License-Identifier: Apache-2.0
"""Original read-only component calculations with shared lazy native access.

The complete L1 inspectors consume these helpers. Ordered masters, missing bases,
rounded display offsets and raw source snapshots deliberately remain distinct.
"""

from typing import Any

from fontlabapp import _native
from fontlabapp.masters.inspect.model import all_names as font_glyph_names  # noqa: F401
from fontlabapp.masters.inspect.model import muted
from fontlabapp.proof.inspect.model import layer_path
from fontlabapp.core.scripting import (
    current_package as _current_package,
    names_font_window_selection as selected_names,
)

COLUMNS = ["Glyph", "Master", "Components", "Offsets", "Layer"]


def current_name() -> str:
    """Read the current native glyph name without touching its FontGate cache."""
    glyph = _native("fontlab").CurrentGlyph()
    return glyph.name if glyph is not None else ""


def component_lists(package: Any, names: Any, masters: Any) -> Any:
    """[(glyph, {master: [base names in order]})] for glyphs with components on any master."""
    rows = []
    for name in names:
        glyph = package.findName(name)
        if glyph is None:
            continue
        lists = {}
        for master in masters:
            layer = glyph.findLayer(master)
            if layer is not None and (not layer.isNull):
                lists[master] = [
                    s.shapeData.componentGlyph for s in layer.shapes if s.isComponent
                ]
        if any(lists.values()):
            rows.append((name, lists))
    return rows


def odd_masters(lists: Any, masters: Any) -> Any:
    """Masters whose component list differs from the first master's."""
    present = [m for m in masters if m in lists]
    if not present:
        return []
    reference = lists[present[0]]
    return [m for m in present if lists[m] != reference]


def item_ink() -> Any:
    """Item text brush: palette Text does not reach item views or spin boxes in FontLab (pale in
    screenshots, measured S-L3), so items get WindowText explicitly.
    """
    QtGui = _native("PythonQt").QtGui
    fontlab = _native("fontlab")
    return QtGui.QBrush(
        QtGui.QColor(fontlab.MainWindow().palette.color(QtGui.QPalette.WindowText))
    )


def frame(dialog: Any, title: Any, width: Any) -> Any:
    """Window title, heading and muted subtitle; returns (root layout, subtitle)."""
    QtGui = _native("PythonQt").QtGui
    dialog.setWindowTitle(title)
    dialog.setMinimumWidth(width)
    root = QtGui.QVBoxLayout(dialog)
    root.setContentsMargins(20, 18, 20, 16)
    root.setSpacing(12)
    heading = QtGui.QLabel(title)
    font = heading.font
    font.setPointSizeF(font.pointSizeF() * 1.35)
    font.setBold(True)
    heading.setFont(font)
    root.addWidget(heading)
    subtitle = QtGui.QLabel()
    subtitle.setWordWrap(True)
    subtitle.setStyleSheet(f"color: {muted(dialog)};")
    root.addWidget(subtitle)
    return (root, subtitle)


def layer_of(glyph: Any, master: Any) -> Any:
    """Preserve the original layer of calculation and native interface."""
    layer = glyph.findLayer(master)
    return None if layer is None or layer.isNull else layer


def counts(layer: Any) -> Any:
    """(components, own contours, auto) for one layer."""
    components = sum(1 for s in layer.shapes if s.isComponent)
    contours = sum(len(s.getContours()) for s in layer.shapes if not s.isComponent)
    return (components, contours, bool(layer.autoLayer))


def pen(color: Any, width: Any = 1.0) -> Any:
    """Preserve the original pen calculation and native interface."""
    QtGui = _native("PythonQt").QtGui
    p = QtGui.QPen(color)
    p.setWidthF(width)
    return p


def has_layer(package: Any, name: Any, master: Any) -> Any:
    """Preserve the original has layer calculation and native interface."""
    glyph = package.findName(name)
    if glyph is None:
        return False
    layer = glyph.findLayer(master)
    return layer is not None and (not layer.isNull)


def missing(package: Any, names: Any, masters: Any, exists: Any = None) -> Any:
    """{missing base: [(glyph, master, reason)]}; exists(name, master) defaults to the font itself."""
    exists = exists or (lambda name, master: has_layer(package, name, master))
    groups = {}
    for name in names:
        glyph = package.findName(name)
        if glyph is None:
            continue
        for master in masters:
            layer = glyph.findLayer(master)
            if layer is None or layer.isNull:
                continue
            for shape in layer.shapes:
                if not shape.isComponent:
                    continue
                base = shape.shapeData.componentGlyph
                if not base:
                    groups.setdefault("(unnamed)", []).append(
                        (name, master, "component without a base name")
                    )
                elif not exists(base, master):
                    reason = (
                        "glyph missing"
                        if package.findName(base) is None
                        else f"no {master} layer"
                    )
                    groups.setdefault(base, []).append((name, master, reason))
    return groups


def component_rows(layer: Any) -> Any:
    """[(base, dx, dy)] for the layer's components, in order."""
    return [
        (s.shapeData.componentGlyph, round(s.transform.dx()), round(s.transform.dy()))
        for s in layer.shapes
        if s.isComponent
    ]


def report(package: Any, names: Any, masters: Any) -> Any:
    """[(glyph, master, components text, offsets text, kind)] for every layer with components."""
    rows = []
    for name in names:
        glyph = package.findName(name)
        if glyph is None:
            continue
        for master in masters:
            layer = glyph.findLayer(master)
            if layer is None or layer.isNull:
                continue
            parts = component_rows(layer)
            if not parts:
                continue
            bases = " + ".join(base for (base, _, _) in parts)
            moves = (
                "  ".join(f"{base} {dx},{dy}" for (base, dx, dy) in parts if dx or dy)
                or "–"
            )
            kind = (
                "auto"
                if layer.autoLayer
                else "mixed"
                if len(parts) != len(layer.shapes)
                else "components"
            )
            rows.append((name, master, bases, moves, kind))
    return rows


def to_csv(rows: Any) -> Any:
    """Preserve the original to csv calculation and native interface."""

    def cell(text: Any) -> Any:
        """Preserve the original cell calculation and native interface."""
        text = str(text)
        return (
            '"' + text.replace('"', '""') + '"'
            if any(c in text for c in ',"\n')
            else text
        )

    lines = [",".join(COLUMNS)] + [",".join(cell(v) for v in row) for row in rows]
    return "\n".join(lines) + "\n"


def usage_index(package: Any, names: Any, masters: Any) -> Any:
    """{base: {composite: [(master, auto)]}} for the whole font, built in one pass."""
    index = {}
    for name in names:
        glyph = package.findName(name)
        if glyph is None:
            continue
        for master in masters:
            layer = glyph.findLayer(master)
            if layer is None or layer.isNull:
                continue
            for base in {
                s.shapeData.componentGlyph for s in layer.shapes if s.isComponent
            }:
                index.setdefault(base, {}).setdefault(name, []).append(
                    (master, layer.autoLayer)
                )
    return index


def source_values(
    package: Any, names: list[str], masters: list[str], *, geometry: bool = False
) -> tuple:
    """Capture native source as plain values, including raw offsets before rounding.

    Only the card tool reads geometry, because the other tools display metadata.
    Base-layer presence participates so newly missing references invalidate actions.
    """
    from fontlabapp.proof.inspectors.model import outline_source

    result = []
    for name in names:
        glyph = package.findName(name)
        if glyph is None or glyph.isNull:
            raise ValueError("Glyph source changed; reopen this tool.")
        layers = []
        for master in masters:
            layer = layer_of(glyph, master)
            if layer is None:
                layers.append((master, None))
                continue
            shapes = []
            for shape in layer.shapes:
                if shape.isComponent:
                    base = shape.shapeData.componentGlyph
                    transform = shape.transform
                    matrix = tuple(
                        getattr(transform, key)()
                        for key in ("m11", "m12", "m21", "m22", "dx", "dy")
                    )
                    shapes.append(
                        (True, base, matrix, has_layer(package, base, master))
                    )
                else:
                    shapes.append((False, len(shape.getContours())))
            layers.append(
                (
                    master,
                    bool(layer.autoLayer),
                    tuple(shapes),
                    (layer.advanceWidth, outline_source(layer)) if geometry else None,
                )
            )
        result.append((name, tuple(layers)))
    return tuple(result)


def glyph_path(layer: Any) -> Any:
    """Reuse the native-verified placed closed/open paths for complete badge outlines."""
    return layer_path(layer)


def current_package() -> Any:
    """Retain the original current-font helper without eager native imports."""
    return _current_package()


def selected_glyphs(package: Any) -> list[Any]:
    """Resolve actual selection, otherwise the non-None current native glyph.

    A valid FontGate CurrentGlyph can be falsey when it has no contours. The badge
    tool tests identity against None and filters unresolved names the same way;
    Compatibility retains selected_names without this current-glyph fallback.
    """
    names = selected_names()
    if not names:
        glyph = _native("fontlab").CurrentGlyph()
        names = [glyph.name] if glyph is not None else []
    glyphs = [package.findName(name) for name in names]
    return [glyph for glyph in glyphs if glyph is not None]
