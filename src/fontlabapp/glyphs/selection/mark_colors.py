# this_file: src/fontlabapp/glyphs/selection/mark_colors.py
# SPDX-License-Identifier: Apache-2.0
"""Add different mark colours to the active Font-window selection.

Independently adapted from Pedro Arilla's Labels/Select different colour.py,
which credits Rainer Erich Scheichelbauer's Select Different Color. Freeze the
initial colour set, then add displayed glyphs of every other colour. Keep the
initial selection. Empty selection is a no-op. Native acceptance is pending.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GlyphMark:
    """One current-font glyph's native hue and Font-window selection state."""

    index: int
    name: str
    mark: int
    selected: bool


def plan(glyphs: tuple[GlyphMark, ...]) -> tuple[int, ...]:
    """Return candidate indices using only the original selected-colour set.

    The native transport maps these candidates into the current filtered chart.
    A glyph absent from that model has no selectable cell. Native marks are
    compared as stored integers, including the unmarked value zero.
    """
    colours = {glyph.mark for glyph in glyphs if glyph.selected}
    if not colours:
        return ()
    return tuple(glyph.index for glyph in glyphs if glyph.mark not in colours)


def select_different_mark_colours() -> tuple[str, ...]:
    """Add displayed different-colour glyphs; return newly selected names.

    Activate the Font window first. No glyph data, Undo step, Output content or
    preference is written. Native failures attempt to remove only new additions;
    an unsafe or failed rollback is reported explicitly.
    """
    from fontlabapp.glyphs.selection._mark_colors_native import select

    return select()
