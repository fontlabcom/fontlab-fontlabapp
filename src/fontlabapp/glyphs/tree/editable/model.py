# this_file: src/fontlabapp/glyphs/tree/editable/model.py
# SPDX-License-Identifier: Apache-2.0
"""Both complete editable-tree policies over local current-font metadata drafts.

Import is host-free. Native capture, UI and model ownership load on use. Edits
change only the local tree; no font, glyph selection, preference or history writer.
"""

from threading import current_thread, main_thread
from typing import Any


def _show(official: bool) -> Any:
    if current_thread() is not main_thread():
        raise RuntimeError("Open the editable glyph tree on the main UI thread.")
    from fontlabapp.glyphs.tree.editable.ui import EditableGlyphTreeDialog
    from fontlabapp.glyphs.tree.model import capture
    from fontlabapp.core.scripting import show_script_dialog

    key = "editable_glyph_tree" if official else "editable_glyph_outline"
    return show_script_dialog(
        lambda parent: EditableGlyphTreeDialog(parent, capture, official=official), key
    )


def show_outline() -> Any:
    """Open part2's local outline with before-row and append-column editing."""
    return _show(False)


def show_tree() -> Any:
    """Open part3's complete editable tree and keyboard/menu/selection policies."""
    return _show(True)
