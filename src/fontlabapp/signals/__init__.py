# this_file: src/fontlabapp/signals/__init__.py
"""Exact Qt signal ownership and callback suppression.

Usage inside FontLab::

    from fly.ap.signals import Scope
    from fly.qt import QtGui
    button = QtGui.QPushButton("Run")
    scope = Scope(lambda error: print(error))
    scope.connect(button.clicked, lambda: print("clicked"))
    # After all button callbacks return:
    scope.finish()
"""

from importlib import import_module
from typing import Any

__all__ = ["track_connection", "disconnect_connections", "quiet_callbacks", "Scope"]
_EXPORTS = {
    "track_connection": "fontlabapp.core.signals.connections",
    "disconnect_connections": "fontlabapp.core.signals.connections",
    "quiet_callbacks": "fontlabapp.core.signals.callbacks",
    "Scope": "fontlabapp.core.signals.scope",
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
