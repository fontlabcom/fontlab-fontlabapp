# this_file: src/fontlabapp/components/graph/model.py
# SPDX-License-Identifier: Apache-2.0
"""Practical FontLab component dependency graphs preserving both elastic lessons.

Both profiles retain their complete fixed-graph oracle and distinct controls.
Captured font data is immutable; node movement changes only an owned scene.
No font, selection, file, preference, Output or history writer is used.
"""

from threading import current_thread, main_thread
from typing import Any


def _show(part: int) -> Any:
    if current_thread() is not main_thread():
        raise RuntimeError("Open component graphs on the main UI thread.")
    from fontlabapp import _native
    from fontlabapp.components.graph.native import capture
    from fontlabapp.components.graph.elastic.ui import panel_type
    from fontlabapp.core.scripting import show_script_dialog

    qt = _native("PythonQt")
    panel = panel_type(qt.QtCore, qt.QtGui)
    return show_script_dialog(
        lambda parent: panel(parent, capture, part), "component_graph" + str(part)
    )


def show() -> Any:
    """Open the clipped-force,30ms,one-arrow part2 dependency graph."""
    return _show(2)


def show_official() -> Any:
    """Open the degree-weighted,40ms,double-arrow part3 dependency graph."""
    return _show(3)
