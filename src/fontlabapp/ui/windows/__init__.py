# this_file: src/fontlabapp/ui/windows/__init__.py
"""Access to existing glyph and preview windows.

Usage inside FontLab::

    from fly.ap.ui.windows import GlyphWindow
    window, workspace = ..., ...  # native objects from the host
    view = GlyphWindow(window, workspace)
    print(view.zoom)
    view.zoom_to(1.0)
    # The wrapper does not own the native window.
"""

from importlib import import_module
from typing import Any

__all__ = ["GlyphWindow", "Preview"]
_EXPORTS = {
    "GlyphWindow": "fontlabapp.qt.views",
    "Preview": "fontlabapp.qt.views",
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
