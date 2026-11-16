# this_file: src/fontlabapp/guides/inspect/model.py
# SPDX-License-Identifier: Apache-2.0
"""Guide calculations and preflight for the measured native dependency-history gap.

Keep imports independent of FontLab and Qt. The guide panels must refuse edits
whose automatic dependants FontLab cannot restore in the same Undo operation.
"""

import math
from typing import Any

from fontlabapp import _native
from fontlabapp.guides.inspect.sources import (
    METRICS,
    font_guide_names,
    layer_path,
    master_layers,
    metric_values,
    muted,
    selected_glyphs,
    source_values,
)


def affected_auto_layers(
    records: tuple[tuple[str, bool, tuple[str, ...]], ...], targets: set[str]
) -> list[str]:
    """Find automatic dependants, including chains through manual composites.

    Combine master records conservatively by glyph name: the measured history
    defect changes glyph dates, which are shared across layers. Walk a finite
    set so circular references do not hang FontLab's UI thread.
    """
    affected = set(targets)
    while True:
        found = {name for name, _, bases in records if affected.intersection(bases)}
        if found.issubset(affected):
            break
        affected.update(found)
    return sorted({name for name, auto, _ in records if auto and name in affected})


def dependency_values(package: Any) -> tuple[tuple[str, bool, tuple[str, ...]], ...]:
    """Read resolved components and auto roles from every registered glyph layer.

    Missing glyphs abort the complete read. Font order comes from this
    package's own FontGate font (``package.fgPackage.glyphs``), not from the
    active font, so a non-active package is read correctly (Issue 250). Never
    convert a native flGlyph through its unsafe fgGlyph getter.
    """
    records = []
    for name in (str(glyph.name) for glyph in package.fgPackage.glyphs):
        glyph = package.findName(name)
        if glyph is None or glyph.isNull:
            raise ValueError("Glyph source changed; reopen this tool.")
        records.extend(
            (
                name,
                bool(layer.autoLayer),
                tuple(
                    shape.shapeData.componentGlyph
                    for shape in layer.shapes
                    if shape.isComponent
                ),
            )
            for layer in glyph.layers
        )
    return tuple(records)


def require_safe_targets(package: Any, targets: set[str]) -> None:
    """Refuse the entire edit before history when native Undo cannot restore it."""
    if not targets:
        return
    records = dependency_values(package)
    if targets.difference(name for name, _, _ in records):
        raise ValueError("Glyph source changed; reopen this tool.")
    blocked = affected_auto_layers(records, targets)
    if blocked:
        raise ValueError(
            "Cannot safely edit guides: FontLab cannot undo changes to automatic "
            "dependants: " + ", ".join(blocked) + ". Choose other glyphs."
        )


HORIZONTAL, VERTICAL, VECTOR = 0x2000, 0x4000, 0x1000
GLYPH_GUIDE = 0x102
TITLE = "Glyph Guides"


def grid(
    direction: int, origin: float, step: float, count: int
) -> list[tuple[float, float, float, str]]:
    """Guide records (x, y, angle, name) of the grid; pure, no font access."""
    records = []
    for i in range(count):
        position = float(origin + i * step)
        if direction in {0, 1}:
            records.append((0.0, position, 0.0, f"Grid H {i + 1}"))
        if direction in {0, 2}:
            records.append((position, 0.0, 90.0, f"Grid V {i + 1}"))
    return records


def guide_record(guide: Any) -> tuple[float, float, float, str]:
    """(x, y, angle in degrees, name) of an flGuideLine; x is 0 for horizontal, y for vertical guides."""
    point = guide.centerPoint
    angle = round(math.degrees(guide.angle), 2) % 180
    (x, y) = (round(point.x(), 2), round(point.y(), 2))
    return (
        0.0 if angle == 0 else x,
        0.0 if angle == 90 else y,
        angle,
        str(guide.name or ""),
    )


def glyph_guides(layer: Any) -> list[Any]:
    return [g for g in layer.guidelines if not g.isHint]


def new_guide(values: tuple[float, float, float, str]) -> Any:
    """A glyph guide through (x, y) at `angle` degrees (0 horizontal, 90 vertical)."""
    (x, y, angle, name) = values
    if not all(math.isfinite(v) for v in (x, y, angle)):
        raise ValueError("Guide coordinates and angle must be finite.")
    QtCore = _native("PythonQt").QtCore
    fontlab = _native("fontlab")
    if angle == 0:
        (line, flags) = (QtCore.QLineF(x, y, x + 100, y), HORIZONTAL)
    elif angle == 90:
        (line, flags) = (QtCore.QLineF(x, y, x, y + 100), VERTICAL)
    else:
        radians = math.radians(angle)
        (line, flags) = (
            QtCore.QLineF(
                x, y, x + 100 * math.cos(radians), y + 100 * math.sin(radians)
            ),
            VECTOR,
        )
    guide = fontlab.flGuideLine(line, flags, GLYPH_GUIDE)
    guide.name = name
    return guide


def add_guides(
    package: Any, jobs: list[tuple[Any, Any, list]], title: str = TITLE
) -> dict[str, int]:
    """Preflight and construct all guides before the original single Undo step.

    Callers provide freshly checked native layers from the bound font. Empty
    jobs do nothing. Refuse auto layers and auto dependants before notification;
    construct every native guide before the first layer is changed. Initialize
    object history directly to avoid an empty Undo entry, and stamp only the
    edited glyphs in UTC before the final history snapshot so Redo restores it.
    """
    work = [(g, layer, values) for g, layer, values in jobs if values]
    if not work:
        return {"layers": 0, "guides": 0}
    if any(layer.autoLayer for _, layer, _ in work):
        raise ValueError("Skip automatic layers before editing guides.")
    require_safe_targets(package, {g.name for g, _, _ in work})
    prepared = [(g, layer, [new_guide(v) for v in values]) for g, layer, values in work]
    layers = [layer for _, layer, _ in prepared]
    glyphs = []
    for glyph, _, _ in prepared:
        if glyph not in glyphs:
            glyphs.append(glyph)
    items = layers + glyphs
    fontlab = _native("fontlab")
    from fontlabapp.core.edit_guards import require_history_scope

    require_history_scope(glyphs, native=fontlab)
    now = _native("PythonQt").QtCore.QDateTime.currentDateTimeUtc
    for item in items:
        item.checkInitHistoryState(0)
    modified = now()
    try:
        for _, layer, values in prepared:
            layer.appendGuidelines(values)
    finally:
        for glyph in glyphs:
            glyph.lastModified = modified
        try:
            fontlab.flItems().notifyChangesApplied(title, items)
            fontlab.UpdateAll()
        finally:
            # Native window observers stamp after history captures this value.
            for glyph in glyphs:
                glyph.lastModified = modified
    return {"layers": len(layers), "guides": sum(len(v) for _, _, v in prepared)}


__all__ = [
    "METRICS",
    "add_guides",
    "affected_auto_layers",
    "dependency_values",
    "font_guide_names",
    "glyph_guides",
    "grid",
    "guide_record",
    "layer_path",
    "master_layers",
    "metric_values",
    "muted",
    "new_guide",
    "require_safe_targets",
    "selected_glyphs",
    "source_values",
]
