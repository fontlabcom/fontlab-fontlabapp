# this_file: src/fontlabapp/proof/text_filter/model.py
# SPDX-License-Identifier: Apache-2.0
"""Filter proof text with the source tool's regular-expression character class.

Adapted from Slobzheninov/Glyphs-Scripts Text Filter (Apache-2.0; see NOTICE).
Modified for Python3.11, lazy FontLab access and shared owned Qt completion.
The character field is a regex character class, not glyph names or a literal set.
Ranges and escapes keep their original meaning; malformed classes raise re.error.
No font or preferences are touched by import or filter_text.
"""

import re
from dataclasses import dataclass
from string import ascii_lowercase, ascii_uppercase
from typing import Any

DEFAULT_CHARACTERS = " ".join(ascii_uppercase + ascii_lowercase) + " . , space"
KEY = "text_filter"


@dataclass(frozen=True)
class SavedText:
    """Keep the three source text fields; Reset preserves input only."""

    input: str = ""
    output: str = ""
    characters: str = DEFAULT_CHARACTERS


def filter_text(text: str, characters: str) -> str:
    """Remove every unmatched code point, preserving order and duplicate characters.

    Enter a-z for a range or \\s for whitespace. An empty or malformed character
    class is an error, as in the source. Do not silently escape or normalize it.
    """
    if not isinstance(text, str) or not isinstance(characters, str):
        raise TypeError("Input and character set must be text.")
    return re.sub(f"[^{characters}]", "", text)


def show() -> Any:
    """Open the complete modeless panel, replacing only its previous owned panel.

    Settings use a dedicated tool namespace. Optional proof tabs use the shared
    literal-text sender and the original font identity; native preservation still
    requires owned FontLab qualification. No application-wide event loop is run.
    """
    from fontlabapp.proof.text_filter.ui import TextFilterDialog
    from fontlabapp.core.scripting import show_script_dialog

    return show_script_dialog(TextFilterDialog, KEY)
