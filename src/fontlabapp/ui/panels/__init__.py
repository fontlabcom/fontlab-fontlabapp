# this_file: src/fontlabapp/ui/panels/__init__.py
"""Existing FontLab panels and owned panel creation.

Usage inside FontLab::

    from fly.ap.ui.panels import Panel, create_panel
    from fly.qt import QtGui
    main = ...  # an existing FontLab main window
    owned = create_panel(main, "Inspector", build=lambda parent: QtGui.QLabel(parent), area="right")
    print(owned.widget.isVisible())
    owned.close()
"""

from importlib import import_module
from typing import Any

__all__ = ["Panel", "Panels", "create_panel"]
_EXPORTS = {
    "Panel": "fontlabapp.qt.views",
    "Panels": "fontlabapp.core.host",
    "create_panel": "fontlabapp.qt.widgets",
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
