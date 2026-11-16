# this_file: src/fontlabapp/ui/widgets/__init__.py
"""Owned widgets, geometry and color dialog helpers.

Usage inside FontLab::

    from fly.ap.ui.widgets import OwnedWidget, create_widget
    from fly.qt import QtGui
    main = ...  # an existing FontLab main window
    owned = create_widget(main, build=lambda parent: QtGui.QLabel(parent))
    assert isinstance(owned, OwnedWidget)
    owned.close()
"""

from importlib import import_module
from typing import Any

__all__ = ["OwnedWidget", "create_widget", "fit_contents", "ColorDialog"]
_EXPORTS = {
    "OwnedWidget": "fontlabapp.qt.widgets",
    "create_widget": "fontlabapp.qt.widgets",
    "fit_contents": "fontlabapp.qt.layouts.content",
    "ColorDialog": "fontlabapp.qt.colors",
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
