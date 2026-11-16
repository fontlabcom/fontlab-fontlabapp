# this_file: src/fontlabapp/qtsafe_api/__init__.py
"""Safe Qt list traversal, main-window discovery and literal text helpers.

Usage inside FontLab::

    from fly.ap.qtsafe_api import qt_list, main_window
    from fly.qt import QtGui
    qt, fontlab = ..., ...  # native modules from the host
    window = main_window(fontlab, qt)
    widgets = qt_list(window.findChildren, QtGui.QWidget)
    print(len(widgets))
"""

from importlib import import_module
from typing import Any

__all__ = [
    "qt_list",
    "main_window",
    "MainWindowNotFound",
    "read_text",
    "set_mime_text",
    "text_fragment",
    "line_edit_type",
]
_EXPORTS = {
    "qt_list": "fontlabapp.qt.safe",
    "main_window": "fontlabapp.qt.safe",
    "MainWindowNotFound": "fontlabapp.qt.safe",
    "read_text": "fontlabapp.qt.literal_text",
    "set_mime_text": "fontlabapp.qt.literal_text",
    "text_fragment": "fontlabapp.qt.literal_text",
    "line_edit_type": "fontlabapp.qt.literal_text",
}


def __getattr__(name: str) -> Any:
    """Resolve one original public object only when it is requested."""
    try:
        source = _EXPORTS[name]
    except KeyError as error:
        raise AttributeError(name) from error
    value = getattr(import_module(source), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """List only the names published by this facade."""
    return sorted(__all__)
