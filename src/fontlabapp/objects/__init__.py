# this_file: src/fontlabapp/objects/__init__.py
"""Phase 1 exposes only FontLab controls and current-font scripting helpers.

Use ``FontLab().current_font()`` and ``FontLab().current_glyphs()`` for the
current font and glyphs inside FontLab. Per-object modules for kerning,
anchors, zones, masters and related data are planned for phase 2.

Usage inside FontLab::

    from fly.ap.objects import FontLab, current_package
    package = current_package()
    if package is not None:
        print(package.id)
        control = FontLab()
        print(control.current_font())
        print(control.current_glyphs())
"""

from importlib import import_module
from typing import Any

__all__ = ["FontLab", "current_package", "font_id", "select_glyphs"]
_EXPORTS = {
    "FontLab": "fontlabapp.core.controls",
    "current_package": "fontlabapp.core.scripting",
    "font_id": "fontlabapp.core.scripting",
    "select_glyphs": "fontlabapp.core.scripting",
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
