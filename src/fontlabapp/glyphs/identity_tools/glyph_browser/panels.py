# this_file: src/fontlabapp/glyphs/identity_tools/glyph_browser/panels.py
"""Reuse complete metadata and name-completion panels inside the browser."""
from typing import Any


def tree(parent: Any) -> Any:
    from fontlabapp.glyphs.tree.model import capture
    from fontlabapp.glyphs.tree.ui import GlyphTreeDialog
    return GlyphTreeDialog(parent, "Glyph Metadata Tree", "glyph_metadata_tree", capture, False)


def completion(parent: Any) -> Any:
    from fontlabapp.glyphs.catalog.native import capture
    from fontlabapp.glyphs.completion.ui import GlyphCompletionDialog
    return GlyphCompletionDialog(parent, capture)


def character(parent: Any) -> Any:
    from .character_info import CharacterInfo
    panel = CharacterInfo(parent)
    panel.timer.stop()
    return panel
