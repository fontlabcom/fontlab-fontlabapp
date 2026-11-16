# this_file: src/fontlabapp/studios/hint_tools/autohint.py
# SPDX-License-Identifier: Apache-2.0
"""Run FontLab's PostScript autohinter on the selected glyphs, in one or all
masters.

What it does:
    For each selected glyph and chosen master, the script runs FontLab's own
    autohinter on the layer. It works from the font's hinting settings
    (alignment zones and standard stems). The table shows the horizontal and
    vertical hint counts before and after. FontLab's source does not touch
    TrueType instructions here.

How it works:
    A non-modal panel lists every glyph and master with its hint counts, or
    the reason why the layer is skipped. Apply reads the font again and
    calls the native flLayer.autohint() on every planned layer, all in one
    Undo step through the shared module fontlabapp.core.history.glyphs. Read-back reports
    a layer that has an outline but no PostScript hints after the call. The
    hint counts and the panel are shared (fontlabapp.hints.postscript,
    fontlabapp.contours.selection.panel.model).

Native call caveat:
    FontLab's source shows that autohint switches the package master
    temporarily,
    writes hinting options and stored hinting data, and can attach hints as
    node links. These effects extend beyond the notified layers; the script
    does not check them. TrueType instructions are separate.

Why this design:
    - The hints come from FontLab's own autohinter, not from a script
      algorithm.
    - The script adds what the menu command does not: every master in one
      step, a count of hints before and after, and one Undo step.
    - Automatic layers and glyphs with automatic layers are never edited. A
      base of automatic composites is skipped unless you tick "Edit bases of
      auto glyphs anyway": the change notification makes FontLab rebuild
      those composites, which can drop their anchors and locks, and Undo
      does not restore them. Locked layers and layers without contours are
      skipped.
    - Apply discloses queued ids and their possible date changes. The script
      does not call UpdateAll (fl#8537).

How to use:
    Set the alignment zones and standard stems in Font Info first. Select
    glyphs in the Font window. Run the script. Choose the current master or
    all masters, check the table and press Autohint. Each Apply is recorded
    as one Undo step.

Benefit:
    A whole selection gets fresh PostScript hints in every master, with the
    counts in view, in one step.

Credit:
    Adapted from the author's own FontLab sample, Apache-2.0
    (hints_autohint.py, "Autohint Selected Layers").
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

TITLE = "Autohint Selected Layers"
KEY = "hints_autohint"


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


def has_outline(layer: Any) -> bool:
    """True when ``layer`` holds contours outside components."""
    return any(not s.isComponent and len(s.contours) for s in layer.shapes)


def layer_note(layer: Any, reason: str) -> str:
    """Return why ``layer`` is not hinted, or "" when it can be."""
    if layer.autoLayer:
        return "auto layer (skipped)"
    if reason:
        return f"{reason} (skipped)"
    if layer.isLocked:
        return "locked layer (skipped)"
    if not has_outline(layer):
        return "no outline (skipped)"
    return ""


def survey(
    package: Any,
    names: Sequence[str],
    masters: Sequence[str],
    facts: Any,
    allow_bases: bool,
) -> list[Row]:
    """Plan every glyph/master. Change nothing."""
    import fontlabapp.hints.postscript as hints  # noqa: PLR0402 - fontlabapp.__getattr__ is native
    import fontlabapp.core.history.glyphs as history  # noqa: PLR0402

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
            note = layer_note(layer, reason)
            rows.append(
                Row(
                    glyph,
                    master,
                    layer,
                    (0, 0) if note else hints.hint_counts(layer),
                    note,
                )
            )
    return rows


def autohint(rows: Sequence[Row], facts: Any, allow_bases: bool) -> dict[str, Any]:
    """Autohint every planned layer as ONE Undo step.

    Return ``{"layers", "glyphs", "after", "mismatches"}``.
    ``after`` maps (glyph, master) to the new hint counts. Read-back reports
    outlined layers with no hints. Nothing to do returns zeros and makes no
    history call.
    """
    import fontlabapp.hints.postscript as hints  # noqa: PLR0402 - fontlabapp.__getattr__ is native
    import fontlabapp.core.history.glyphs as history  # noqa: PLR0402

    todo = [r for r in rows if not r.note]
    if not todo:
        return {"pending_updates": (), "pending_note": "", "layers": 0, "glyphs": 0, "after": {}, "mismatches": []}
    glyphs = list({str(r.glyph.name): r.glyph for r in todo}.values())

    def mutate() -> None:
        for row in todo:
            row.layer.autohint()

    def read_back() -> list[str]:
        return [
            f"{row.glyph.name} · {row.master}: outline has no PostScript hints after autohint"
            for row in todo
            if has_outline(row.layer) and hints.hint_counts(row.layer) == (0, 0)
        ]

    done = history.commit(
        TITLE, [r.layer for r in todo], glyphs, mutate,
        operation="geometry", facts=facts, allow_bases=allow_bases, read_back=read_back,
    )  # fmt: skip
    return {"pending_note": done.pending_note, 
        "pending_updates": done.pending_updates,
        "layers": len(todo),
        "glyphs": len(glyphs),
        "after": {
            (str(r.glyph.name), r.master): hints.hint_counts(r.layer) for r in todo
        },
        "mismatches": list(done.mismatches),
    }

