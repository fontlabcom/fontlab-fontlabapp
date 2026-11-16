# this_file: src/fontlabapp/metrics/worksheet/model.py
# SPDX-License-Identifier: Apache-2.0
"""Open either complete numeric-delegate lesson as a glyph spacing worksheet.

Keep all eight original cells editable even without a font. Capture every actual
selected glyph-layer advance, then compare four local A-times-B candidates.
Refresh retains factors and refuses unstable context. Reset changes local factors
only. Close cancels pending input. Native PythonQt/full-font preservation remains
pending qualification. See NOTICE for original identity and complete notices.
"""

from threading import current_thread, main_thread
from typing import Any


def _show(official: bool) -> Any:
    if current_thread() is not main_thread():
        raise RuntimeError("Open the spacing worksheet on the main UI thread.")
    from fontlabapp import _native
    from fontlabapp.metrics.worksheet.capture import capture
    from fontlabapp.core.scripting import show_script_dialog
    from fontlabapp.metrics.worksheet.ui import panel_type

    qt = _native("PythonQt")
    kind = panel_type(qt.QtCore, qt.QtGui)
    key = "spacing_worksheet_official" if official else "spacing_worksheet"
    return show_script_dialog(
        lambda parent: kind(parent, capture, official=official), key
    )


def show() -> Any:
    """Open part2: string defaults, Factor headers, framed editors, 640×460."""
    return _show(False)


def show_official() -> Any:
    """Open part3: integer defaults, native numeric headers, frameless editors."""
    return _show(True)
