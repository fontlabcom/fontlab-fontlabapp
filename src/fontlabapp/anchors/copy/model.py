# this_file: src/fontlabapp/anchors/copy/model.py
# SPDX-License-Identifier: Apache-2.0
"""Original anchor-copy arithmetic with preconstructed, dependency-safe writes.

New pins get the appearance FontLab otherwise infers only on Redo/reopen.
Existing pin style and expressions remain native values, untouched by copying.
"""

from typing import Any

from fontlabapp import _native
from fontlabapp.anchors.inspect.model import anchor_points, attachment_layer_of
from fontlabapp.guides.inspect.model import affected_auto_layers, dependency_values

TITLE = "Copy Anchors from Glyph"
ORIGIN_ERROR = "FontLab cannot restore an existing anchor moved to 0, 0 with Redo. Choose an unscaled copy or other targets."
APPEARANCE = {
    "top": 5,
    "_bottom": 5,
    "bottom": 6,
    "_top": 6,
    "left": 7,
    "_left": 7,
    "right": 8,
    "_right": 8,
    "center": 1,
    "_center": 1,
}
# Native name defaults: flpinpoint.cpp detectAppearance; flpinpoint.h Appearance.


def layer_of(glyph: Any, master: str) -> Any:
    """Read an existing master layer without manufacturing missing layers."""
    layer = glyph.findLayer(master)
    return None if layer is None or layer.isNull else layer


def plan(source: Any, target: Any, scale: bool, replace: bool) -> list:
    """[(name, old or None, new or None)]; new None means removal."""
    ratio = (
        target.advanceWidth / source.advanceWidth
        if scale and source.advanceWidth
        else 1.0
    )
    wanted = {
        name: (round(x * ratio), y) for name, (x, y) in anchor_points(source).items()
    }
    current = anchor_points(target)
    rows = [(name, current.get(name), point) for name, point in wanted.items()]
    if replace:
        rows += [
            (name, point, None) for name, point in current.items() if name not in wanted
        ]
    return rows


def require_safe_targets(package: Any, targets: set[str]) -> None:
    """Reject the whole batch while no history or native mutation exists yet."""
    records = dependency_values(package)
    if targets.difference(name for name, _, _ in records):
        raise ValueError("Glyph source changed; reopen this tool.")
    blocked = affected_auto_layers(records, targets)
    if blocked:
        raise ValueError(
            "Cannot safely copy anchors: FontLab cannot undo changes to automatic "
            "dependants: " + ", ".join(blocked) + ". Choose other glyphs."
        )


def _prepare(layer: Any, edits: list) -> list:
    """Construct every native point/pin before any target's history is opened."""
    pins = {pin.name: pin for pin in layer.anchors}
    QtCore, fontlab = _native("PythonQt").QtCore, _native("fontlab")
    prepared = []
    for name, point in edits:
        existing = pins.get(name)
        value = None if point is None else QtCore.QPointF(*point)
        if point is not None and existing is None:
            pin = fontlab.flPinPoint(value)
            pin.name, pin.anchor = name, True
            pin.appearance = APPEARANCE.get(name.lower(), 0)
            value = pin
        prepared.append((existing, value))
    return prepared


def _write(layer: Any, prepared: list) -> None:
    """Keep original native pins when moving; add/remove only the planned pins."""
    for existing, value in prepared:
        if value is None:
            layer.removeAnchor(existing)
        elif existing is None:
            layer.addAnchor(value)
        else:
            existing.point = value


def _apply(work: list, title: str) -> None:
    """One native Undo, including recoverable partial writes; no manual rollback."""
    glyphs = list({g.name: g for g, _, _ in work}.values())
    fontlab = _native("fontlab")
    from fontlabapp.core.edit_guards import require_history_scope

    require_history_scope(glyphs, native=fontlab)
    items = [layer for _, layer, _ in work] + glyphs
    for item in items:
        item.checkInitHistoryState(0)
    modified = _native("PythonQt").QtCore.QDateTime.currentDateTimeUtc()
    try:
        for _, layer, prepared in work:
            _write(layer, prepared)
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


def run(
    source_glyph: Any,
    glyphs: list,
    masters: list[str],
    scale: bool,
    replace: bool,
    *,
    package: Any,
    title: str = TITLE,
) -> dict:
    """Keep original skips/counts and refuse unknown masters before collecting work."""
    if source_glyph is None:
        raise ValueError("Choose an existing source glyph.")
    if len(set(masters)) != len(masters) or set(masters).difference(package.masters):
        raise ValueError("Masters changed; reopen this tool.")
    work, skipped = [], []
    for glyph in glyphs:
        if glyph.name == source_glyph.name:
            continue
        for master in masters:
            source, target = layer_of(source_glyph, master), layer_of(glyph, master)
            if source is None or target is None:
                continue
            if target.autoLayer:
                skipped.append(f"{glyph.name}/{master}")
                continue
            edits = [
                (name, new)
                for name, old, new in plan(source, target, scale, replace)
                if old != new
            ]
            if edits:
                work.append((glyph, target, edits))
    if work:
        for _, layer, edits in work:
            existing = {p.name for p in layer.anchors}
            if any(point == (0, 0) and name in existing for name, point in edits):
                raise ValueError(ORIGIN_ERROR)
        require_safe_targets(package, {glyph.name for glyph, _, _ in work})
        prepared = [(g, layer, _prepare(layer, edits)) for g, layer, edits in work]
        _apply(prepared, title)
    return {
        "anchors": sum(len(e) for _, _, e in work),
        "layers": len(work),
        "skipped": skipped,
    }


def source_values(package: Any, names: list[str], masters: list[str]) -> tuple:
    """Freeze raw source/target coordinates, widths, expressions and pin attributes."""
    records = []
    for name in names:
        if package.findName(name) is None:
            raise ValueError("Glyph source changed; reopen this tool.")
        layers = []
        for master in masters:
            layer = attachment_layer_of(package, name, master)
            value = (
                None
                if layer is None
                else (
                    bool(layer.autoLayer),
                    float(layer.advanceWidth),
                    tuple(
                        (
                            p.name,
                            p.point.x(),
                            p.point.y(),
                            p.appearance,
                            p.anchor,
                            p.expressionX,
                            p.expressionY,
                        )
                        for p in layer.anchors
                    ),
                )
            )
            layers.append((master, value))
        records.append((name, tuple(layers)))
    return dependency_values(package), tuple(records)
