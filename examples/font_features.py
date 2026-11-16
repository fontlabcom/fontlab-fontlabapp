# this_file: examples/font_features.py
"""Inside FontLab, pass an explicit FontParts font whose features has apply().

    editor = edit_features(font)
    # editor.refresh() (Revert) reloads text changed elsewhere, e.g. by Undo.
    # editor.close() disconnects callbacks.

The handle exposes .block_control (Prefix, then each feature tag),
.text_control, .tag_control with .add_button, .remove_button, .status,
.apply_button, .revert_button and .diagnostic. Fontport fonts are edited block
by block through font.features.get_blocks()/set_blocks(); other models with
features.apply edit one whole text. Typing is staged; .dirty reports unapplied
edits. Apply writes every block in one call, checks the readback and calls back
with (font, whole_text). Code is stored, never compiled or executed; Fontport
refuses blocks that FontLab's Undo splitter could not restore. Each block keeps
its own line ending; mixed endings are shown but not rewritten. In-session
storage is exact, but FontLab 9.0.9783 drops trailing non-ASCII characters and
turns a block-final CRLF into LF when a VFJ is reopened (fontlab/fl#8510). FontLab's
Undo/Redo actions reload the editor. No document is opened, saved or selected implicitly by this example.
"""

from typing import Any

from fly.ap.fontui import features_editor


def edit_features(font: Any) -> Any:
    """Return the retained original editor over a borrowed explicit font."""
    editor = features_editor(font)
    editor.widget.resize(800, 600)
    editor.widget.show()
    return editor
