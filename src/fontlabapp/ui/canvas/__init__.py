# this_file: src/fontlabapp/ui/canvas/__init__.py
"""Drawing overlays and glyph editor painters.

Usage inside FontLab::

    from fly.ap.ui.canvas import EditorPainters, AFTER_NATIVE_LAYER
    qt, fontlab = ..., ...  # native modules from the host
    painters = EditorPainters(qt, fontlab, error_sink=lambda error, owner: print(error))
    token = painters.register(AFTER_NATIVE_LAYER, lambda context: None)
    painters.remove(token)
"""

from importlib import import_module
from typing import Any

__all__ = [
    "Drawing",
    "EditorPainters",
    "PaintContext",
    "AFTER_NATIVE_LAYER",
    "LAYER_FILTERS",
]
_EXPORTS = {
    "Drawing": "fontlabapp.qt.painting.drawing",
    "EditorPainters": "fontlabapp.qt.painting.editor",
    "PaintContext": "fontlabapp.qt.painting.editor",
    "AFTER_NATIVE_LAYER": "fontlabapp.qt.painting.editor",
    "LAYER_FILTERS": "fontlabapp.qt.painting.editor",
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
