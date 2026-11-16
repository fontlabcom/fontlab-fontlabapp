# this_file: src/fontlabapp/guides/rewrite/model.py
# SPDX-License-Identifier: Apache-2.0
"""Preconstruct complete guide rewrites, retaining native guide style and hints.

Use only freshly bound registered glyphs/layers. Preflight the whole batch before
copying native values. Reuse the measured guide history protocol: initialize each
object, stamp edited glyphs in UTC, then notify once, including after a partial
native write error so the user retains Undo. Do not manually restore font fields.
"""

from typing import Any

from fontlabapp import _native
from fontlabapp.guides.records import (
    DIRECTIONS,
    direction_of,
    matches,
    parse_row,
    scaled,
    target_records,
)
from fontlabapp.guides.inspect.model import (
    glyph_guides,
    guide_record,
    new_guide,
    require_safe_targets,
)

TITLE = "Glyph Guides"


def _preflight(package: Any, work: list) -> None:
    """Refuse direct automatic layers and all unsafe dependants before history."""
    if any(layer.autoLayer for _, layer, _ in work):
        raise ValueError("Skip automatic layers before editing guides.")
    require_safe_targets(package, {glyph.name for glyph, _, _ in work})


def _prepare(layer: Any, records: list) -> list:
    """Copy unchanged values with complete style; construct every new guide now."""
    copy = _native("fontlab").flGuideLine
    pool = [(guide_record(g), g) for g in glyph_guides(layer)]
    planned = []
    for record in records:
        index = next((i for i, (old, _) in enumerate(pool) if old == record), None)
        planned.append(
            copy(pool.pop(index)[1]) if index is not None else new_guide(record)
        )
    return planned


def _write(layer: Any, prepared: list) -> None:
    """Keep native hints and any retained native guides without duplicating them."""
    layer.removeGuides(True, True)
    left = [guide_record(g) for g in glyph_guides(layer)]
    add = []
    for guide in prepared:
        record = guide_record(guide)
        if record in left:
            left.remove(record)
        else:
            add.append(guide)
    if add:
        layer.appendGuidelines(add)


def _apply(prepared: list, title: str) -> None:
    """Record one native history operation for a fully preconstructed batch."""
    glyphs = []
    for glyph, _, _ in prepared:
        if glyph not in glyphs:
            glyphs.append(glyph)
    items = [layer for _, layer, _ in prepared] + glyphs
    fontlab = _native("fontlab")
    from fontlabapp.core.edit_guards import require_history_scope

    require_history_scope(glyphs, native=fontlab)
    for item in items:
        item.checkInitHistoryState(0)
    modified = _native("PythonQt").QtCore.QDateTime.currentDateTimeUtc()
    try:
        for _, layer, values in prepared:
            _write(layer, values)
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


def replace_guides(package: Any, jobs: list, title: str = TITLE) -> dict[str, int]:
    """Write exact ordered records; an empty list removes the layer's guides."""
    work = [
        (g, layer, values)
        for g, layer, values in jobs
        if values != [guide_record(v) for v in glyph_guides(layer)]
    ]
    if not work:
        return {"layers": 0}
    _preflight(package, work)
    prepared = [(g, layer, _prepare(layer, records)) for g, layer, records in work]
    _apply(prepared, title)
    return {"layers": len(work)}


def clear(package: Any, jobs: list, title: str = TITLE) -> dict[str, int]:
    """Keep complete chosen native guide copies and report actual removals."""
    work = [
        (g, layer, keep)
        for g, layer, keep in jobs
        if [guide_record(v) for v in keep]
        != [guide_record(v) for v in glyph_guides(layer)]
    ]
    if not work:
        return {"layers": 0, "removed": 0, "left": 0}
    _preflight(package, work)
    copy = _native("fontlab").flGuideLine
    prepared = [(g, layer, [copy(v) for v in keep]) for g, layer, keep in work]
    before = sum(len(glyph_guides(layer)) for _, layer, _ in work)
    expected = sum(len(keep) for _, _, keep in work)
    _apply(prepared, title)
    after = sum(len(glyph_guides(layer)) for _, layer, _ in work)
    return {"layers": len(work), "removed": before - after, "left": after - expected}


__all__ = [
    "DIRECTIONS",
    "clear",
    "direction_of",
    "matches",
    "parse_row",
    "replace_guides",
    "scaled",
    "target_records",
]
