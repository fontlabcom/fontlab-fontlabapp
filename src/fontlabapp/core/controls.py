# this_file: src/fontlabapp/core/controls.py
"""Direct native controls without proxies for user-owned fonts or glyphs."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Self

from fontlabapp import _native
from fontlabapp.qt.views import _PANEL_IDS, GlyphWindow, Panel, Preview
from fontlabapp.qt.widgets import OwnedWidget


class FontLab:
    """Lazy native application control; construct inside FontLab.

    Catalogue calls return native JSON dictionaries. ``native_font`` and
    ``native_glyph`` return raw host values, without additional Python proxies.
    Closing this context removes only overlays/custom UI created through it.
    """

    def __init__(self, application: Any = None) -> None:
        if application is None:
            from fontlabapp import Application

            application = Application(with_ui=True, with_preflib=False)
        self.application = application
        self._owned = []

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        for resource in reversed(self._owned):
            resource.close()
        self._owned.clear()

    def _own(self, resource):
        self._owned.append(resource)
        return resource

    def tool(self, name: str, **arguments: Any) -> Any:
        """Call native fontpr directly, preserving native errors and arguments."""
        return _native("fontpr").call(name, **arguments)

    def list_fonts(self) -> Any:
        return self.tool("list_fonts")

    def fonts(self) -> list[dict[str, Any]]:
        """Return native open-font records, retaining their native ids."""
        return self.list_fonts()["fonts"]

    def open_font(self, **arguments: Any) -> Any:
        return self.tool("open_font", **arguments)

    def new_font(self, **arguments: Any) -> Any:
        return self.tool("new_font", **arguments)

    def save_font(self, **arguments: Any) -> Any:
        return self.tool("save_font", **arguments)

    def close_font(self, **arguments: Any) -> Any:
        return self.tool("close_font", **arguments)

    def current_font(self) -> Any:
        return self.tool("get_active_font")

    def current_glyphs(self) -> Any:
        return self.tool("get_current_glyphs")

    def list_glyphs(self, **arguments: Any) -> Any:
        return self.tool("list_glyphs", **arguments)

    def font_info(self, **arguments: Any) -> Any:
        return self.tool("get_font_info", **arguments)

    def glyph_info(self, **arguments: Any) -> Any:
        return self.tool("get_glyph", **arguments)

    def glyph(self, name: str, **arguments: Any) -> Any:
        """Read glyph JSON by name; optional font/layer fields pass to fontpr."""
        return self.glyph_info(glyph_name=name, **arguments)

    def font_metrics(self, **arguments: Any) -> Any:
        return self.tool("get_font_metrics", **arguments)

    def glyph_metrics(self, **arguments: Any) -> Any:
        return self.tool("get_glyph_metrics", **arguments)

    def set_font_metrics(self, **arguments: Any) -> Any:
        return self.tool("set_font_metrics", **arguments)

    def set_glyph_metrics(self, **arguments: Any) -> Any:
        return self.tool("set_glyph_metrics", **arguments)

    def activate_font(self, **arguments: Any) -> Any:
        return self.tool("set_active_font", **arguments)

    def activate_glyph(self, **arguments: Any) -> Any:
        return self.tool("set_active_glyph", **arguments)

    def list_actions(self) -> Any:
        return self.tool("list_actions")

    def run_actions(self, **arguments: Any) -> Any:
        return self.tool("run_actions", **arguments)

    def output(self) -> str:
        return _native("fontlab").GetProperty("output")

    @property
    def native_font(self) -> Any:
        return _native("fontlab").CurrentFont()

    @property
    def native_glyph(self) -> Any:
        return _native("fontlab").CurrentGlyph()

    def panel(self, name: str) -> Panel:
        """Reuse ApplicationUI's panel catalogue; unknown names fail clearly."""
        entries = self._ui().panels
        if name not in entries or entries[name].get("widget") is None:
            raise LookupError(f"FontLab panel is unavailable: {name}")
        return Panel(
            entries[name]["widget"], self.application.main, _PANEL_IDS.get(name)
        )

    def _ui(self):
        if not hasattr(self.application, "ui"):
            from fontlabapp.core.application.ui import ApplicationUI

            self.application.ui = ApplicationUI(self.application)
        return self.application.ui

    @property
    def preview(self) -> Preview:
        return Preview(self.panel("preview"), owner=self)

    def glyph_windows(self) -> list[GlyphWindow]:
        """Find actual GlyphWindows without activating or closing any view."""
        return [
            GlyphWindow(w, self.application.ws, owner=self)
            for w in self._ui().glyphWindows().values()
        ]

    def glyph_window(self) -> GlyphWindow:
        canvas = self.application.ws.getActiveCanvas()
        for window in self.glyph_windows():
            if window.canvas == canvas:
                return window
        raise LookupError("No active Glyph window")

    def create_panel(
        self,
        title: str,
        build: Callable | None = None,
        *,
        area: str = "right",
        compact: bool = True,
    ) -> OwnedWidget:
        """Create an owned registered dock; float it when MainWindow is hidden.

        Layouts are compact (6 px / 4 px) unless ``compact=False``.
        """
        from fontlabapp.qt.widgets import create_panel

        return self._own(create_panel(self.application.main, title, build, area, compact=compact))

    def create_dialog(
        self, title: str, build: Callable | None = None, *, compact: bool = True
    ) -> OwnedWidget:
        """Show an owned modeless QDialog composed by build(content).

        Layouts are compact (6 px / 4 px) unless ``compact=False``.
        """
        from fontlabapp.qt.widgets import create_dialog

        return self._own(create_dialog(self.application.main, title, build, compact=compact))

    def create_widget(
        self,
        parent: Any = None,
        build: Callable | None = None,
        *,
        show: bool = True,
        compact: bool = True,
    ) -> OwnedWidget:
        """Compose a visible owned tool QWidget, or a child of explicit parent.

        Layouts are compact (6 px / 4 px) unless ``compact=False``.
        """
        from fontlabapp.qt.widgets import create_widget

        return self._own(
            create_widget(
                parent or self.application.main,
                build,
                floating=parent is None,
                show=show,
                compact=compact,
            )
        )
