# this_file: src/fontlabapp/anchors/inspect/model.py
# SPDX-License-Identifier: Apache-2.0
"""Preserve original anchor coordinates, compatibility and attachment arithmetic.

The three read-only L1 tools share native access and transformed outlines with
verified Components/Proof helpers. Raw source snapshots retain sub-unit drift,
while the original displayed points deliberately round to integral font units.
"""

from typing import Any

from fontlabapp import _native
from fontlabapp.components.inspect.model import (
    current_package,
    font_glyph_names,
    frame,
    glyph_path,
    item_ink,
    muted,
    pen,
    selected_glyphs,
    source_values as geometry_source,
)
from fontlabapp.core.scripting import (
    names_font_window_selection as exact_selected_names,
)


def cloud_layer_of(glyph: Any, master: Any) -> Any:
    """Retain the original cloud layer of values and missing-data rules."""
    layer = glyph.findLayer(master)
    return None if layer is None or layer.isNull else layer


def anchor_names(glyphs: Any, masters: Any) -> list[str]:
    """Anchor names by frequency on the glyphs."""
    counts = {}
    for glyph in glyphs:
        for master in masters:
            layer = cloud_layer_of(glyph, master)
            for pin in layer.anchors if layer is not None else []:
                counts[pin.name] = counts.get(pin.name, 0) + 1
    return sorted(counts, key=lambda n: (-counts[n], n))


def cloud(glyphs: Any, master: Any, name: Any) -> list[tuple[str, int, int]]:
    """[(glyph name, x, y)] of the named anchor on one master."""
    points = []
    for glyph in glyphs:
        layer = cloud_layer_of(glyph, master)
        for pin in layer.anchors if layer is not None else []:
            if pin.name == name:
                points.append((glyph.name, round(pin.point.x()), round(pin.point.y())))
    return points


def anchor_sets(
    package: Any, names: Any, masters: Any
) -> list[tuple[str, dict[str, list[str] | None]]]:
    """[(glyph, {master: [anchor names] or None})] for glyphs with anchors on any master.

    Auto layers map to None: FontLab regenerates their anchors from the base glyph (lazily, per
    master, minus the anchor the mark consumed), so they are shown but never compared.
    """
    rows = []
    for name in names:
        glyph = package.findName(name)
        if glyph is None:
            continue
        (sets, has_anchors) = ({}, False)
        for master in masters:
            layer = glyph.findLayer(master)
            if layer is not None and (not layer.isNull):
                names_here = sorted(pin.name for pin in layer.anchors)
                has_anchors = has_anchors or bool(names_here)
                sets[master] = None if layer.autoLayer else names_here
        if has_anchors:
            rows.append((name, sets))
    return rows


def is_mismatch(sets: Any) -> bool:
    """Retain the original is mismatch values and missing-data rules."""
    return len({tuple(v) for v in sets.values() if v is not None}) > 1


def attachment_layer_of(package: Any, name: Any, master: Any) -> Any:
    """Retain the original attachment layer of values and missing-data rules."""
    glyph = package.findName(name)
    if glyph is None:
        return None
    layer = glyph.findLayer(master)
    return None if layer is None or layer.isNull else layer


def anchor_points(layer: Any) -> dict[str, tuple[int, int]]:
    """Retain the original anchor points values and missing-data rules."""
    return {
        pin.name: (round(pin.point.x()), round(pin.point.y())) for pin in layer.anchors
    }


def classify(package: Any, names: Any, master: Any) -> tuple[list[str], list[str]]:
    """(bases, marks): names with plain anchors, names with _anchors, on one master."""
    (bases, marks) = ([], [])
    for name in names:
        layer = attachment_layer_of(package, name, master)
        if layer is None:
            continue
        found = [pin.name for pin in layer.anchors]
        if any(n.startswith("_") for n in found):
            marks.append(name)
        if any(not n.startswith("_") for n in found):
            bases.append(name)
    return (bases, marks)


def families(base_layer: Any, mark_layer: Any) -> list[str]:
    """Anchor names X with X on the base and _X on the mark."""
    (base, mark) = (anchor_points(base_layer), anchor_points(mark_layer))
    return [name for name in base if not name.startswith("_") and "_" + name in mark]


def attachment(base_layer: Any, mark_layer: Any, family: Any) -> tuple[int, int] | None:
    """(dx, dy) that puts the mark's _family anchor on the base's family anchor, or None."""
    (base, mark) = (anchor_points(base_layer), anchor_points(mark_layer))
    if family not in base or "_" + family not in mark:
        return None
    ((bx, by), (mx, my)) = (base[family], mark["_" + family])
    return (bx - mx, by - my)


def selected_names() -> list[str]:
    """Retain Mark Preview's current-glyph fallback using explicit None identity."""
    names = exact_selected_names()
    if not names:
        glyph = _native("fontlab").CurrentGlyph()
        names = [glyph.name] if glyph is not None else []
    return names


def source_values(
    package: Any, names: list[str], masters: list[str], geometry_names: list[str]
) -> tuple:
    """Capture ordered raw anchor values and only the outlines actually displayed.

    Geometry names are frozen by the panel before a scan and retained for later
    source checks. Changing a base/mark selector therefore validates the previous
    display first, then captures the new pair without treating intended UI input
    as a font edit. No native value-object equality participates.
    """
    result = []
    for name in names:
        glyph = package.findName(name)
        if glyph is None or glyph.isNull:
            raise ValueError("Glyph source changed; reopen this tool.")
        layers = []
        for master in masters:
            layer = cloud_layer_of(glyph, master)
            values = (
                None
                if layer is None
                else (
                    bool(layer.autoLayer),
                    tuple(
                        (pin.name, pin.point.x(), pin.point.y())
                        for pin in layer.anchors
                    ),
                )
            )
            layers.append((master, values))
        result.append((name, tuple(layers)))
    return tuple(result), geometry_source(
        package, geometry_names, masters, geometry=True
    )
