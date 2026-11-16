# this_file: src/fontlabapp/shortcuts/__init__.py
"""Key press routing for PythonQt widget subclasses.

Usage inside FontLab::

    from fly.ap.shortcuts import key_press_handler
    from fly.qt import QtGui
    class SearchField(QtGui.QLineEdit):
        keyPressEvent = key_press_handler(QtGui.QLineEdit,
            lambda widget, event: False)
    field = SearchField()
"""

from importlib import import_module
from typing import Any

__all__ = ["key_press_handler"]
_EXPORTS = {
    "key_press_handler": "fontlabapp.qt.events.key",
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
