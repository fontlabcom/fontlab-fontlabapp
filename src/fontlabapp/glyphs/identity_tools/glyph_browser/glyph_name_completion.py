# this_file: src/fontlabapp/glyphs/identity_tools/glyph_browser/glyph_name_completion.py
# SPDX-License-Identifier: Apache-2.0
"""Draft text with completions taken from the glyph names of the current font.

What: Opens a modeless panel with a text area. As you type, the panel offers
the exact glyph names of the current font as completions, so you can write
lists of glyph names (for a class, a test string or a note) without typos.
Typing at least three characters, or pressing Ctrl+E, opens the completion
list. The vocabulary is the complete glyph-name list in font order.

Use: Open a font. Run Names > Glyph Name Completion. Type a draft and pick
names from the list. Press Refresh to reload the vocabulary after the font
changed; your draft stays. Select and copy the text with the normal text
shortcuts. Close the panel when you are done. The draft is not saved anywhere.

Safety: The panel only reads glyph names. Your draft lives in the panel and is
lost when the panel closes. The tool writes no font data, selection, history,
preference, file or Output text, and it never copies text by itself.
Standard text selection and copy stay under your control.

Source: Original workflow built on the shared App completion panel
(fontlabapp.glyphs.completion.model), Apache-2.0.
Requires App>=1.2.0 and fontlab-fly in FontLab 9 Python 3.11.
"""

from typing import Any


def main() -> Any:
    """Open the shared glyph-name completion panel, or replace the open one."""
    from fontlabapp.glyphs.completion.model import show

    return show()


if __name__ == "__main__":
    main()
