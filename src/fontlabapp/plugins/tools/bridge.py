# this_file: src/fontlabapp/plugins/tools/bridge.py
"""Guard FontLab Python tool callbacks and map viewport events to glyph units."""

from typing import Any

from fontlabapp.plugins import snapshot
from fontlabapp.plugins.backend import active_glyph_map
from fontlabapp.plugins.reporter import Reporter
from fontlabapp.plugins.tool import ToolContext, ToolEvent
from fontlabapp.qt.painting.view import glyph_point


class _ToolPainter(Reporter):
    """Use the Reporter renderer only while this tool is active."""

    def __init__(self, tool: Any) -> None:
        self.tool = tool
        self.needs_components = tool.needs_components

    def compute(self, glyph: snapshot.GlyphSnapshot) -> list[Any]:
        """Delegate pure mark computation to the active tool."""
        marks = self.tool.marks(glyph)
        self._computed = True
        return marks

    def paint(self, context: Any, qt: Any, sink: Any, capture: Any = None) -> None:
        """Invalidate a Tool after missing/failed capture, even for repeated errors."""
        self._computed = False
        try:
            super().paint(context, qt, sink, capture)
        finally:
            if not self._computed:
                try:
                    self.tool.marks(None)
                except Exception as error:  # noqa: BLE001 - legacy Tool boundary
                    self._report(sink, error)


def _glyph_point(canvas: Any, view: Any) -> tuple[float, float]:
    """Invert backend's glyph/block map after FontLab removes pan and zoom."""
    transform = active_glyph_map(canvas)
    if transform is None:
        raise ValueError("No active glyph on this canvas")
    return glyph_point(transform.glyph, transform.block, canvas.mapFromViewport(view))


class ToolBridge:
    """Strongly own one plugin, its overlay adapter and native callbacks."""

    def __init__(self, tool: Any, services: Any) -> None:
        self.tool, self.services = tool, services
        self.context = ToolContext(services, needs_components=tool.needs_components)
        self.painter = _ToolPainter(tool)
        self.paint_token: int | None = None
        self.active = False
        self._last: tuple[float, float] | None = None
        self._reported: set[tuple[str, str]] = set()

    def _error(self, name: str, error: Exception) -> None:
        """Report each callback failure once, including a failing sink."""
        key = name, f"{type(error).__name__}: {error}"
        if key in self._reported:
            return
        self._reported.add(key)
        try:
            self.services.sink(error, self.tool)
        except Exception:  # noqa: BLE001, S110 - native callback boundary
            pass

    def _call(self, name: str, action: Any) -> bool:
        """Return False for any native or plugin failure."""
        try:
            return bool(action())
        except Exception as error:  # noqa: BLE001 - native callback boundary
            self._error(name, error)
            return False

    def activate(self) -> bool:
        """Register the overlay, then activate the tool; unwind on failure."""

        def action() -> bool:
            if self.active:
                return True
            self.paint_token = self.services.painters.register(
                self.painter, self.services.qt, self.services.sink
            )
            try:
                self.tool.activate(self.context)
            except Exception:
                self.services.painters.remove(self.paint_token)
                self.paint_token = None
                raise
            self.active = True
            self._last = None
            return True

        return self._call("activate", action)

    def deactivate(self) -> bool:
        """Remove the painter even when plugin deactivation fails."""

        def action() -> bool:
            if not self.active and self.paint_token is None:
                return True
            self.active = False
            self._last = None
            try:
                self.tool.deactivate()
            finally:
                token, self.paint_token = self.paint_token, None
                if token is not None:
                    self.services.painters.remove(token)
            return True

        return self._call("deactivate", action)

    def _event(
        self, event: Any, canvas: Any, *, clicks: int = 1, key: bool = False
    ) -> ToolEvent:
        """Copy Qt event fields before the native callback invalidates them."""
        qt = self.services.qt.QtCore.Qt
        if key and self._last is None:
            point = canvas.viewPort.mapFromGlobal(self.services.qt.QtGui.QCursor.pos())
        elif key:
            point = self.services.qt.QtCore.QPointF(*self._last)
        else:
            point = event.localPos()
        view_x, view_y = float(point.x()), float(point.y())
        x, y = _glyph_point(canvas, point)
        if not key:
            self._last = view_x, view_y
        flags = int(event.modifiers())
        return ToolEvent(
            x,
            y,
            view_x,
            view_y,
            0 if key else int(event.buttons()),
            bool(flags & int(qt.ShiftModifier)),
            bool(flags & int(qt.AltModifier)),
            bool(flags & int(qt.ControlModifier)),
            bool(flags & int(qt.MetaModifier)),
            str(event.text()) if key else None,
            clicks,
            float(canvas.scale()),
        )

    def _dispatch(
        self, name: str, event: Any, canvas: Any, *, clicks: int = 1, key: bool = False
    ) -> bool:
        """Call one handler only while active; keys never swallow shortcuts."""
        if not self.active:
            return False

        def action() -> bool:
            mapped = self._event(event, canvas, clicks=clicks, key=key)
            handled = bool(getattr(self.tool, name)(mapped))
            return False if key else handled

        return self._call(name, action)

    def mousePressed(self, event: Any, canvas: Any) -> bool:
        return self._dispatch("press", event, canvas)

    def mouseMoved(self, event: Any, canvas: Any) -> bool:
        return self._dispatch("move", event, canvas)

    def mouseReleased(self, event: Any, canvas: Any) -> bool:
        return self._dispatch("release", event, canvas)

    def mouseDoubleClicked(self, event: Any, canvas: Any) -> bool:
        return self._dispatch("double_click", event, canvas, clicks=2)

    def keyPressed(self, event: Any, canvas: Any) -> bool:
        return self._dispatch("key_down", event, canvas, key=True)

    def keyReleased(self, event: Any, canvas: Any) -> bool:
        return self._dispatch("key_up", event, canvas, key=True)
