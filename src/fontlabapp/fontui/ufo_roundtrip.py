# this_file: src/fontlabapp/fontui/ufo_roundtrip.py
# SPDX-License-Identifier: Apache-2.0
"""UFO Roundtrip Inspector: owned staging plus a complete semantic report."""

from typing import Any

__all__ = ['show']
_HANDLES = []


def show(font: Any, parent: Any = None) -> Any:
    """Show an owned inspector over one borrowed font, without implicit execution."""
    from fontlabapp import _native
    from fontlabapp.fontui import _construct
    from fontlabapp.fontui.ufo_roundtrip_editor import RoundtripEditor
    from fontlabapp.qt.safe import main_window

    qt = _native('PythonQt')
    host = parent if parent is not None else main_window(_native('fontlab'), qt)
    owner = _construct(RoundtripEditor, font, host)
    _HANDLES.append(owner)
    owner.on_closed = lambda item: _HANDLES.remove(item)
    try:
        owner.widget.setWindowFlags(qt.QtCore.Qt.Window)
        owner.widget.setWindowTitle('UFO Roundtrip Inspector')
        owner.widget.resize(800, 600)
        owner.widget.show()
    except BaseException:
        owner.close()
        raise
    return owner
