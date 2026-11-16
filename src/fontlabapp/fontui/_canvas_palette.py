# this_file: src/fontlabapp/fontui/_canvas_palette.py
# SPDX-License-Identifier: Apache-2.0
"""Per-paint semantic colors for the two glyph canvases; never change preferences."""

from typing import Any as _Any

from fontlabapp.qt.properties import value as _value

__all__ = []

_DARK = {
    "background": "#202124", "box": "#292b30", "guide": "#737780",
    "baseline": "#a6aab2", "fill": "#737b86", "outline": "#eeeeee",
    "component": "#587a9c", "handle": "#a5a9b0", "on_curve": "#72baff",
    "off_curve": "#ffa17e", "start": "#81d991", "selected": "#ffb35c",
    "anchor": "#e6a0e6", "missing": "#a5a9b0", "band": "#72baff",
    "overlay": "#91bdea", "highlight": "#ff81a2", "bearing": "#72baff",
    "kern_negative": "#ff8585", "kern_positive": "#81d991", "glyph": "#eeeeee",
}


def _native_dark() -> bool | None:
    """Read only the two declared bools; missing/old native bindings use Qt."""
    try:
        import fontlab

        preferences = fontlab.flPreferences()
        canvas = _value(preferences, "generalDarkGlyph")
        chrome = _value(preferences, "isDark")
    except (ImportError, AttributeError, TypeError, RuntimeError):
        return None
    if type(canvas) is bool and type(chrome) is bool:
        return canvas and chrome
    return None


def _canvas_colors(widget: _Any, light: dict[str, str]) -> dict[str, str]:
    """Resolve native canvas policy, or the actual owned widget's Qt palette.

    An explicit palette on the canvas is the private controlled-fixture boundary.
    An inherited chrome palette must not override FontLab's light-canvas policy.
    """
    from PythonQt import QtCore, QtGui

    palette = _value(widget, "palette")
    group = QtGui.QPalette.Active if _value(widget, "isActiveWindow") else QtGui.QPalette.Inactive
    enabled = _value(widget, "isEnabled")
    if not enabled:
        group = QtGui.QPalette.Disabled
    native = None if widget.testAttribute(QtCore.Qt.WA_SetPalette) else _native_dark()
    background = palette.color(group, QtGui.QPalette.Base)
    dark = background.lightness() < 128 if native is None else native
    colors = {key: _DARK[key] if dark else color for key, color in light.items()}
    colors["selection_background"] = "#315984" if dark else "#d8eaff"
    colors["selection_foreground"] = "#ffffff" if dark else "#202124"
    if native is None:
        colors["background"] = background.name()
        foreground = palette.color(group, QtGui.QPalette.Text).name()
        for key in ("outline", "glyph"):
            if key in colors:
                colors[key] = foreground
        colors["selection_background"] = palette.color(group, QtGui.QPalette.Highlight).name()
        colors["selection_foreground"] = palette.color(group, QtGui.QPalette.HighlightedText).name()
    if not enabled:
        # Keep disabled marks readable while removing their active semantic accents.
        for key, color in colors.items():
            if key not in ("background", "box", "fill", "selection_background", "selection_foreground"):
                gray = QtGui.QColor(color).lightness()
                colors[key] = QtGui.QColor(gray, gray, gray).name()
    return colors
