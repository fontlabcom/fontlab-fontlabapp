# this_file: src/fontlabapp/glyphs/selection/_mark_colors_native.py
# SPDX-License-Identifier: Apache-2.0
"""Guarded additive transport through the native filtered Font-window model.

oldFL/pFontLab.cxx Select and Selected call FontChartItemModel.findGlyph with
match_name=false. That read-only GID lookup returns only existing chart cells;
it neither rebuilds the filter nor inserts missing cells. Never clear selection
or call UpdateAll. Keep the Font-window guard ahead of every native writer.
"""

from typing import Any

from fontlabapp import _native
from fontlabapp.glyphs.selection.mark_colors import GlyphMark
from fontlabapp.core.scripting import _require_selection_window, current_package


def _guard(package_id: int, panel: Any) -> None:
    """Reject changed packages or windows before touching legacy selection."""
    _require_selection_window(package_id)
    workspace = _native("fontlab").flWorkspace.instance()
    if (
        workspace.activeFontPanel != panel
        or workspace.currentPackage.id != package_id
        or current_package(package_id) is None
    ):
        raise ValueError("The source font or Font window changed; run again.")


def _capture(fl: Any) -> tuple[GlyphMark, ...]:
    """Read exact native hues and checked selection values without fg getters."""
    font = fl.font
    rows = []
    for index in range(len(font)):
        glyph = font[index]
        selected = fl.Selected(index)
        if selected not in (False, True) or selected is None:
            raise ValueError("Cannot read the Font-window selection.")
        rows.append(GlyphMark(index, str(glyph.name), int(glyph.mark), bool(selected)))
    return tuple(rows)


def _rollback(
    fl: Any, package_id: int, panel: Any, before: tuple[GlyphMark, ...]
) -> None:
    """Remove only actual new selections, while the same window remains active."""
    for glyph in before:
        _guard(package_id, panel)
        if not glyph.selected and fl.Selected(glyph.index):
            fl.Select(glyph.index, 0)
    if _capture(fl) != before:
        raise RuntimeError("Selection rollback verification failed.")


def select() -> tuple[str, ...]:
    """Apply the frozen-colour policy using additive, display-mapped writes."""
    from fontlabapp.glyphs.selection import mark_colors as api

    package = current_package()
    if package is None:
        raise ValueError("Open a font and activate its Font window.")
    _require_selection_window(package.id)
    panel = _native("fontlab").flWorkspace.instance().activeFontPanel
    _guard(package.id, panel)
    fl = _native("FL").fl
    before = _capture(fl)
    indices = api.plan(before)
    _guard(package.id, panel)
    if _capture(fl) != before:
        raise ValueError("The source glyphs, marks or selection changed; run again.")
    try:
        for index in indices:
            _guard(package.id, panel)
            fl.Select(index)
        _guard(package.id, panel)
        after = _capture(fl)
        if any(
            a.name != b.name
            or a.mark != b.mark
            or (b.selected and not a.selected)
            or (a.selected and not b.selected and a.index not in indices)
            for a, b in zip(after, before, strict=True)
        ):
            raise RuntimeError("Native selection postcondition failed.")
    except Exception as error:
        try:
            _rollback(fl, package.id, panel, before)
        except Exception as rollback_error:
            raise RuntimeError(
                "Selection additions may remain; rollback was unsafe or failed."
            ) from rollback_error
        raise RuntimeError(
            "Selection failed; the original selection was restored."
        ) from error
    return tuple(
        a.name
        for a, b in zip(after, before, strict=True)
        if a.selected and not b.selected
    )
