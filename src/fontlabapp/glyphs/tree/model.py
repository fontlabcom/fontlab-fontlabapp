# this_file: src/fontlabapp/glyphs/tree/model.py
# SPDX-License-Identifier: Apache-2.0
"""Read-only current-font adaptations of both archived Simple Tree Model lessons.

Keep ordered glyphs, all Unicode assignments and local modification dates in a
complete expandable hierarchy. No selection, font or preference writer is used.
Part2 retains row/column status and noneditable EditRole text; part3 is DisplayRole
only. Import remains host-free; native capture and widgets load only on use.
"""

from threading import current_thread, main_thread
from time import monotonic
from typing import Any

from fontlabapp.qt.tables.filter.model import Table
from fontlabapp.qt.trees.data import Tree, check_deadline


def from_table(table: Table, *, deadline: float | None = None) -> Tree:
    """Convert every observed glyph in order; missing values stay explicit."""
    if not isinstance(table, Table):
        raise TypeError("Glyph metadata must be a complete immutable Table.")
    limit = monotonic() + 2.0 if deadline is None else deadline
    rows = []
    for name, codes, modified in table.rows:
        check_deadline(limit)
        parent = len(rows)
        rows.append((-1, (name, codes or "Not encoded")))
        rows.extend(
            (parent, ("Unicode", code)) for code in (codes.split() or ["Not encoded"])
        )
        rows.append((parent, ("Modified", modified or "Not recorded")))
    check_deadline(limit)
    return Tree(("Glyph or field", "Assignment or local date"), tuple(rows))


def capture(*, deadline: float) -> Tree:
    """Use the existing full-font source fence under the caller's one deadline."""
    from fontlabapp.glyphs.catalog.native import capture as metadata

    return from_table(metadata(deadline=deadline), deadline=deadline)


def _show(outline: bool) -> Any:
    if current_thread() is not main_thread():
        raise RuntimeError("Open the glyph tree on the main UI thread.")
    from fontlabapp.glyphs.tree.ui import GlyphTreeDialog
    from fontlabapp.core.scripting import show_script_dialog

    key = "glyph_metadata_outline" if outline else "glyph_metadata_tree"
    title = "Glyph Metadata Outline" if outline else "Glyph Metadata Tree"
    return show_script_dialog(
        lambda parent: GlyphTreeDialog(parent, title, key, capture, outline), key
    )


def show_outline() -> Any:
    """Show the full part2 read-only outline and selected row/column status."""
    return _show(True)


def show_tree() -> Any:
    """Show the full part3 read-only expandable glyph-metadata tree."""
    return _show(False)
