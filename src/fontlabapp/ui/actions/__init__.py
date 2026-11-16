# this_file: src/fontlabapp/ui/actions/__init__.py
"""Live FontLab action descriptors and lookup.

Usage inside FontLab::

    from fly.ap.ui.actions import Action, ActionDisabledError, live
    matches = live().menu.find("kern")
    try:
        if matches:
            matches[0].trigger()
    except ActionDisabledError:
        pass
"""

from importlib import import_module
from typing import Any

__all__ = [
    "Action",
    "Actions",
    "GlyphAction",
    "GlyphActions",
    "ActionDisabledError",
    "live",
]
_EXPORTS = {
    "Action": "fontlabapp.core.host",
    "Actions": "fontlabapp.core.host",
    "GlyphAction": "fontlabapp.core.host",
    "GlyphActions": "fontlabapp.core.host",
    "ActionDisabledError": "fontlabapp.core.host",
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
