# this_file: src/fontlabapp/glyphs/pattern.py
# SPDX-License-Identifier: Apache-2.0
"""Author Qt 5 patterns and inspect complete captured FontLab glyph-name matches.

All four original syntaxes, editable combo histories and native captures remain.
No font, selection, file, clipboard, Output, preference or history writer is used.
"""

from threading import current_thread, main_thread
from typing import Any


def _capture(*, deadline: float) -> tuple[str, ...]:
    from fontlabapp.glyphs.catalog.native import capture
    from fontlabapp.glyphs.completion.model import vocabulary

    return vocabulary(capture(deadline=deadline), deadline=deadline)


def show() -> Any:
    """Open the owned modeless lab through the current FontLab Qt 5 binding."""
    if current_thread() is not main_thread():
        raise RuntimeError("Open Glyph Name Pattern Lab on the main UI thread.")
    from fontlabapp import _native
    from fontlabapp.qt.regexp.ui import panel_type
    from fontlabapp.core.scripting import show_script_dialog

    qt = _native("PythonQt")
    kind = panel_type(qt.QtCore, qt.QtGui)
    return show_script_dialog(lambda parent: kind(parent, _capture), "glyph_pattern")
