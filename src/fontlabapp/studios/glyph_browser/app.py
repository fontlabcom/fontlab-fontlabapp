# this_file: src/fontlabapp/studios/glyph_browser/app.py
# SPDX-License-Identifier: Apache-2.0
"""Find glyphs, inspect character metadata and draft completed names together."""
from typing import Any


def show(*, parent: Any = None, font: Any = None, package: Any = None, tab: str | None = None) -> Any:
    import fontlabapp.fontui as fontui  # noqa: PLR0402 - studio boundary uses public module
    Route, assemble = fontui.identity_route, fontui.identity_studio

    routes = (
        Route("Character Info", lambda owner: fontui.identity_panel("glyphs.identity_tools.glyph_browser.panels", "character", owner), refresh="refresh", preview="refresh", preview_target=lambda panel: (panel.shown_name, None)),
        Route("Glyph Finder", lambda owner: fontui.identity_panel("glyphs.identity_tools.glyph_browser.glyph_finder", "Finder", owner), refresh="refresh", preview="refresh", glyph_column=0),
        Route("Glyph Metadata Tree", lambda owner: fontui.identity_panel("glyphs.identity_tools.glyph_browser.panels", "tree", owner), refresh="refresh", preview="refresh", buttons=("refresh_button",), glyph_column=0, glyph_table="view"),
        Route("Glyph Name Completion", lambda owner: fontui.identity_panel("glyphs.identity_tools.glyph_browser.panels", "completion", owner), refresh="refresh", preview="refresh"),
    )
    return assemble("Glyph Browser", routes, preview="tglyph", parent=parent, font=font, package=package, tab=tab)
