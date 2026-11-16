# this_file: src/fontlabapp/qt/views.py
"""Existing native panel, Preview and Glyph-view access without view ownership."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any, Self

from fontlabapp import _native
from fontlabapp.qt.safe import qt_list
from fontlabapp.qt.painting.drawing import Drawing

# Native PanelId enum (flworkspace.h), rather than toggling QAction state.
_PANEL_IDS = {
    "preview": 21,
    "output": 22,
    "glyph": 10,
    "fonts": 11,
    "anchors_pins": 13,
    "node": 15,
    "guide": 16,
    "layers_masters": 9,
    "transform": 4,
    "history": 8,
    "classes": 18,
    "features": 19,
    "kerning": 23,
    "metrics": 24,
    "image": 25,
    "truetype_hinting": 27,
    "brush": 14,
    "color": 2,
    "elements": 1,
    "fontaudit": 5,
    "font_info": 12,
    "gallery": 28,
    "help": 31,
    "lookups": 35,
    "measurements": 33,
    "scripting_python": 20,
    "selections": 36,
    "stroke": 7,
    "pairs_phrases": 29,
    "source": 32,
    "tables": 34,
    "variations": 26,
    "view": 3,
}


class Panel:
    """Explicit visibility/focus for an existing user-owned native panel."""

    def __init__(
        self, widget: Any, main: Any = None, panel_id: int | None = None
    ) -> None:
        self.widget, self._main, self._id = widget, main, panel_id

    @property
    def visible(self) -> bool:
        return self.widget.isVisible()

    def set_visible(self, visible: bool) -> Panel:
        if not isinstance(visible, bool):
            raise TypeError("Panel visibility must be bool")
        if self._main is not None and self._id is not None:
            self._main.showPanel(self._id, visible)
        else:
            self.widget.setVisible(visible)
        return self

    def show(self) -> Self:
        return self.set_visible(True)

    def hide(self) -> Self:
        return self.set_visible(False)

    def focus(self) -> Self:
        self.show()
        self.widget.raise_()
        self.widget.setFocus()
        return self


class Preview:
    """The real FontPreviewWidget scoped under the Preview panel."""

    def __init__(self, panel: Any, owner: Any = None) -> None:
        qt = _native("PythonQt").QtGui
        descriptor = panel if isinstance(panel, Panel) else Panel(panel)
        matches = [
            w
            for w in qt_list(descriptor.widget.findChildren, qt.QWidget)
            if w.className() == "FontPreviewWidget"
            and str(w.objectName) == "widgetPreview"
        ]
        if len(matches) != 1:
            raise LookupError("Preview panel has no unique FontPreviewWidget")
        self.widget, self.panel, self._owner = matches[0], descriptor, owner

    def set_text(self, text: str, *, process: bool = True) -> Preview:
        self.widget.setText(text, process)
        return self

    def set_font_size(self, points: float) -> Preview:
        if not math.isfinite(points) or points <= 0:
            raise ValueError("Font size must be positive and finite")
        self.widget.setFontSize(float(points))
        return self

    def set_color(self, color: str) -> Preview:
        self.widget.setTextColor(_native("PythonQt").QtGui.QColor(color))
        return self

    def set_auto_size(self, enabled: bool) -> Preview:
        self.widget.setAutoSize(enabled)
        return self

    def set_waterfall(self, sizes: list[float]) -> Preview:
        if any(not math.isfinite(n) or n <= 0 for n in sizes):
            raise ValueError("Waterfall sizes must be positive and finite")
        self.widget.setTextWaterfall(sizes)
        return self

    def draw(
        self, callback: Callable[[Any], None], *, coordinates: str = "pixels"
    ) -> Drawing:
        if coordinates != "pixels":
            raise ValueError(
                "Preview drawing supports pixels only; no native text-to-font map is exposed"
            )
        from fontlabapp.qt.painting.drawing import Drawing

        drawing = Drawing(self.widget, callback)
        return self._owner._own(drawing) if self._owner else drawing


def _viewport(widget: Any) -> Any:
    """The Glyph window's ``widgetViewport`` child.

    Some PythonQt builds expose named children as attributes; FontLab 9 does
    not ("GlyphWindow has no attribute named 'widgetViewport'"), so fall back
    to the child with that objectName.
    """
    try:
        return widget.widgetViewport
    except AttributeError:
        pass
    qt = _native("PythonQt").QtGui
    for child in qt_list(widget.findChildren, qt.QWidget):
        if child.objectName == "widgetViewport":
            return child
    raise LookupError("Glyph window has no widgetViewport child")


class GlyphWindow:
    """Native view access; owns neither the view nor its font."""

    def __init__(self, widget: Any, workspace: Any, owner: Any = None) -> None:
        self.widget, self.viewport, self._workspace = (
            widget,
            _viewport(widget),
            workspace,
        )
        self._owner = owner

    @property
    def canvas(self) -> Any:
        qt = _native("PythonQt").QtGui
        # widgetViewport is a YLighterWidget container. The actual flCanvas
        # belongs to an inner QWidget, as verified in the live native runtime.
        for widget in [self.viewport, *qt_list(self.viewport.findChildren, qt.QWidget)]:
            canvas = self._workspace.getCanvasForViewport(widget)
            if canvas is not None:
                return canvas
        raise LookupError("Glyph window has no native canvas")

    @property
    def zoom(self) -> float:
        return self.canvas.scale()

    def zoom_to(self, scale: float, center: Any = None) -> GlyphWindow:
        if not math.isfinite(scale) or scale <= 0:
            raise ValueError("Zoom must be positive and finite")
        canvas = self.canvas
        canvas.zoomTo(center if center is not None else canvas.viewPoint, float(scale))
        return self

    def pan_to(self, x: float, y: float) -> GlyphWindow:
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("Canvas center must be finite")
        return self.zoom_to(self.zoom, _native("PythonQt").QtCore.QPointF(x, y))

    def to_pixels(self, x: float, y: float) -> Any:
        return self.canvas.mapToViewportF(_native("PythonQt").QtCore.QPointF(x, y))

    def from_pixels(self, x: float, y: float) -> Any:
        return self.canvas.mapFromViewport(_native("PythonQt").QtCore.QPointF(x, y))

    def draw(
        self, callback: Callable[[Any], None], *, coordinates: str = "pixels"
    ) -> Drawing:
        """Paint over this one glyph window (pixels or canvas units).

        For painters called once per laid-out glyph with a glyph-to-canvas
        map, over all glyph windows, use ``fontlabapp.qt.painting.editor``.
        """
        from fontlabapp.qt.painting.drawing import Drawing

        if coordinates not in {"pixels", "canvas"}:
            raise ValueError(
                "Glyph drawing supports pixels or canvas; glyph-local font coordinates need an explicit native item map"
            )
        canvas = self.canvas
        drawing = Drawing(
            canvas.viewPort,
            callback,
            canvas=canvas if coordinates == "canvas" else None,
        )
        return self._owner._own(drawing) if self._owner else drawing
