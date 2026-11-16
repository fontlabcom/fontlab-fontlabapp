# this_file: src/fontlabapp/menus/__init__.py
"""Live menus and owned QAction registration.

Usage inside FontLab::

    from fly.ap.menus import OwnedMenus
    qt, fontlab = ..., ...  # native modules from the host
    owner = OwnedMenus(qt, fontlab, error_sink=lambda error, source: print(error))
    token = owner.add_action("Edit", "My command", lambda: None)
    owner.remove(token)
    owner.close()
"""

from importlib import import_module
from typing import Any

__all__ = ["Menu", "MenuBar", "OwnedMenus", "OWNED_MENU_TITLE", "live"]
_EXPORTS = {
    "Menu": "fontlabapp.core.host",
    "MenuBar": "fontlabapp.core.host",
    "OwnedMenus": "fontlabapp.qt.menus",
    "OWNED_MENU_TITLE": "fontlabapp.qt.menus",
    "live": "fontlabapp.core.host",
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
