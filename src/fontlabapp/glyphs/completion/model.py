# this_file: src/fontlabapp/glyphs/completion/model.py
# SPDX-License-Identifier: Apache-2.0
"""Draft text with completions from the current font's complete glyph-name list.

The two complete archived custom-completer variants retain different key,
focus, suffix and menu policies. Refresh replaces only the observed vocabulary;
draft text stays local to the owned modeless panel. Standard text selection and
copy remain available. No font, selection, preference, file or history is edited.
"""

from threading import current_thread, main_thread
from time import monotonic
from typing import Any

from fontlabapp.qt.tables.filter.model import Table


def vocabulary(table: Table, *, deadline: float | None = None) -> tuple[str, ...]:
    """Keep every exact glyph name in observed order; reject incomplete input."""
    if not isinstance(table, Table):
        raise TypeError("Completion requires a complete immutable glyph Table.")
    limit = monotonic() + 2.0 if deadline is None else deadline
    names, seen = [], set()
    for row in table.rows:
        if monotonic() >= limit:
            raise TimeoutError("Glyph vocabulary scan expired; no partial result.")
        name = row[0]
        if not name or name in seen:
            raise ValueError("Glyph vocabulary contains an empty or duplicate name.")
        seen.add(name)
        names.append(name)
    if monotonic() >= limit:
        raise TimeoutError("Glyph vocabulary scan expired; no partial result.")
    return tuple(names)


def _show(official: bool) -> Any:
    if current_thread() is not main_thread():
        raise RuntimeError("Open glyph completion on the main UI thread.")
    from fontlabapp.glyphs.catalog.native import capture
    from fontlabapp.glyphs.completion.ui import GlyphCompletionDialog
    from fontlabapp.core.scripting import show_script_dialog

    key = "glyph_completion_official" if official else "glyph_completion"
    return show_script_dialog(
        lambda parent: GlyphCompletionDialog(parent, capture, official=official), key
    )


def show() -> Any:
    """Open part2 alphabetic triggers, New/Close and Vocabulary controls."""
    return _show(False)


def show_official() -> Any:
    """Open part3 punctuation/modifier, focus, popup and About/Exit controls."""
    return _show(True)
