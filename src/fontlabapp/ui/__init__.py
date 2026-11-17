# this_file: src/fontlabapp/ui/__init__.py
"""Owned UI factories for FontLab windows and widgets.

Usage inside FontLab::

    from fly.ap.ui import create_widget
    from fly.qt import QtGui
    main = ...  # an existing FontLab main window
    owned = create_widget(main, build=lambda parent: QtGui.QLabel(parent))
    print(owned.widget.isVisible())
    owned.close()
"""

from importlib import import_module
from typing import Any

__all__ = [
    "OwnedWidget",
    "compact",
    "compact_dialog",
    "compact_layout",
    "controls_box",
    "create_dialog",
    "create_panel",
    "create_widget",
    "frameless",
    "split_view",
]
_EXPORTS = {
    "OwnedWidget": "fontlabapp.qt.widgets",
    "compact": "fontlabapp.qt.compact",
    "compact_dialog": "fontlabapp.qt.compact",
    "compact_layout": "fontlabapp.qt.compact",
    "controls_box": "fontlabapp.qt.compact",
    "frameless": "fontlabapp.qt.compact",
    "split_view": "fontlabapp.qt.compact",
    "create_dialog": "fontlabapp.qt.widgets",
    "create_panel": "fontlabapp.qt.widgets",
    "create_widget": "fontlabapp.qt.widgets",
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
