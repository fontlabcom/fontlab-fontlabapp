# this_file: src/fontlabapp/studios/hint_tools/removal.py
# SPDX-License-Identifier: Apache-2.0
"""Remove PostScript stem hints from the selected glyphs, horizontal and/or
vertical.

What it does:
    For each selected glyph and chosen master, the script removes the
    horizontal hints, the vertical hints or both from the layer. FontLab's
    source does not touch plain guidelines or TrueType instructions here. The
    table shows the hint counts before and after.

How it works:
    A non-modal panel lists every glyph and master with its hint counts, or
    the reason why the layer is skipped. A layer without hints in the chosen
    directions is listed and skipped. Apply reads the font again and calls
    the native flLayer.removeHints(horizontal, vertical) on every planned
    layer, all in one Undo step through the shared module fontlabapp.core.history.glyphs.
    After the write it counts the hints again and reports any layer that
    still has hints in a chosen direction. The hint counts and the panel are
    shared (fontlabapp.hints.postscript, fontlabapp.contours.selection.panel.model).

Why this design:
    - The removal is FontLab's own call, so hints are removed exactly as the
      menu command removes them.
    - The script adds what the menu command does not: every master in one
      step, one direction only, the counts in view and one Undo step.
    - Automatic layers and glyphs with automatic layers are never edited. A
      base of automatic composites is skipped unless you tick "Edit bases of
      auto glyphs anyway": the change notification makes FontLab rebuild
      those composites, which can drop their anchors and locks, and Undo
      does not restore them. Locked layers are skipped.
    - Apply discloses queued ids and their possible date changes. The script
      does not call UpdateAll (fl#8537).

How to use:
    Select glyphs in the Font window. Run the script. Tick the directions,
    choose the current master or all masters, check the table and press
    Remove Hints. Each Apply is recorded as one Undo step.

Benefit:
    Clean hint-free layers before a new autohint pass or a TrueType-only
    export, in every master, in one step.

Credit:
    Adapted from the author's own FontLab sample, Apache-2.0
    (hints_remove.py, "Remove PostScript Hints").
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

TITLE = "Remove PostScript Hints"
KEY = "hints_remove"


@dataclass(frozen=True)
class Row:
    """One glyph/master layer. ``before`` is (horizontal, vertical) hints; ``note`` set: skipped."""

    glyph: Any
    master: str
    layer: Any
    before: tuple[int, int] = (0, 0)
    note: str = ""


def _valid(layer: Any) -> bool:
    """True for a real native layer object."""
    return layer is not None and not layer.isNull


def chosen(counts: tuple[int, int], horizontal: bool, vertical: bool) -> int:
    """Return how many of ``counts`` lie in the chosen directions."""
    return (counts[0] if horizontal else 0) + (counts[1] if vertical else 0)


def direction_word(horizontal: bool, vertical: bool) -> str:
    """Return "horizontal ", "vertical " or "" for the chosen directions."""
    if horizontal and vertical:
        return ""
    return "horizontal " if horizontal else "vertical "


def layer_note(layer: Any, reason: str, horizontal: bool, vertical: bool) -> str:
    """Return why ``layer`` keeps its hints, or "" when hints will be removed."""
    import fontlabapp.hints.postscript as hints  # noqa: PLR0402 - fontlabapp.__getattr__ is native

    if layer.autoLayer:
        return "auto layer (skipped)"
    if reason:
        return f"{reason} (skipped)"
    if layer.isLocked:
        return "locked layer (skipped)"
    if not chosen(hints.hint_counts(layer), horizontal, vertical):
        return f"no {direction_word(horizontal, vertical)}hints"
    return ""


def survey(
    package: Any,
    names: Sequence[str],
    masters: Sequence[str],
    facts: Any,
    allow_bases: bool,
    horizontal: bool = True,
    vertical: bool = True,
) -> list[Row]:
    """Plan every glyph/master. Change nothing. No direction raises ValueError."""
    import fontlabapp.hints.postscript as hints  # noqa: PLR0402 - fontlabapp.__getattr__ is native
    import fontlabapp.core.history.glyphs as history  # noqa: PLR0402

    if not (horizontal or vertical):
        raise ValueError("Tick at least one hint direction.")
    rows: list[Row] = []
    for name in names:
        glyph = package.findName(name)
        if glyph is None or glyph.isNull:
            continue
        reason = history.refusal(
            facts, str(glyph.name), "geometry", allow_bases=allow_bases
        )
        for master in masters:
            layer = glyph.findLayer(master)
            if not _valid(layer):
                rows.append(Row(glyph, master, None, note="no layer in this master"))
                continue
            note = layer_note(layer, reason, horizontal, vertical)
            counts = (0, 0) if layer.autoLayer or reason else hints.hint_counts(layer)
            rows.append(Row(glyph, master, layer, counts, note))
    return rows


def remove_hints(
    rows: Sequence[Row], horizontal: bool, vertical: bool, facts: Any, allow_bases: bool
) -> dict[str, Any]:
    """Remove the chosen hints from every planned layer as ONE Undo step.

    Return ``{"layers", "glyphs", "removed", "mismatches"}``. Nothing to do
    returns zeros and makes no history call. A refusal raises ValueError; a
    failure after history started raises RuntimeError with the Undo hint.
    """
    import fontlabapp.hints.postscript as hints  # noqa: PLR0402 - fontlabapp.__getattr__ is native
    import fontlabapp.core.history.glyphs as history  # noqa: PLR0402

    todo = [r for r in rows if not r.note]
    if not todo:
        return {"pending_updates": (), "pending_note": "", "layers": 0, "glyphs": 0, "removed": 0, "mismatches": []}
    glyphs = list({str(r.glyph.name): r.glyph for r in todo}.values())

    def mutate() -> None:
        for row in todo:
            row.layer.removeHints(horizontal, vertical)

    def read_back() -> list[str]:
        found = []
        for row in todo:
            h, v = hints.hint_counts(row.layer)
            h, v = (h if horizontal else 0), (v if vertical else 0)
            if h or v:
                found.append(
                    f"{row.glyph.name} · {row.master}: {h} horizontal and {v} vertical hints remain"
                )
        return found

    done = history.commit(
        TITLE, [r.layer for r in todo], glyphs, mutate,
        operation="geometry", facts=facts, allow_bases=allow_bases, read_back=read_back,
    )  # fmt: skip
    removed = sum(
        chosen(r.before, horizontal, vertical)
        - chosen(hints.hint_counts(r.layer), horizontal, vertical)
        for r in todo
    )
    return {"pending_note": done.pending_note, 
        "pending_updates": done.pending_updates,
        "layers": len(todo),
        "glyphs": len(glyphs),
        "removed": removed,
        "mismatches": list(done.mismatches),
    }

