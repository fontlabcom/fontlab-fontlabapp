# this_file: src/fontlabapp/studios/glyph_labels/app.py
# SPDX-License-Identifier: Apache-2.0
"""Glyph notes, tags and marks retain their existing guarded writers in one shell."""
from typing import Any


def show(*, parent: Any = None, font: Any = None, package: Any = None, tab: str | None = None) -> Any:
    import fontlabapp.fontui as fontui  # noqa: PLR0402 - studio boundary uses public module
    Route, assemble = fontui.identity_route, fontui.identity_studio

    routes = (
        Route("Batch Glyph Notes", lambda owner: fontui.identity_panel("glyphs.identity_tools.glyph_labels.batch_glyph_notes", "_dialog_type", owner, factory_type=True), preview="refresh", apply="apply", glyph_column=0),
        Route("Glyph Notes", lambda owner: fontui.identity_panel("glyphs.identity_tools.glyph_labels.glyph_notes", "_dialog_type", owner, factory_type=True), preview="edited", apply="apply", apply_label="Save note", glyph_column=0, glyph_table="list"),
        Route("Glyph Tags", lambda owner: fontui.identity_panel("glyphs.identity_tools.glyph_labels.controls", "tags", owner), preview="update_buttons", apply="apply_staged", buttons=("add_button", "remove_button")),
        Route("Mark Color Palette", lambda owner: fontui.identity_panel("glyphs.identity_tools.glyph_labels.controls", "marks", owner), apply="apply_staged"),
        Route("Select by Mark", lambda owner: fontui.identity_panel("glyphs.identity_tools.glyph_labels.select_by_mark", "SelectByMark", owner), refresh="reload", preview="ensure_snapshot", apply="select_rows", apply_label="Select in Font window", buttons=("select_button",)),
        Route("Select Different Mark Colours", lambda owner: fontui.identity_panel("glyphs.identity_tools.glyph_labels.different_colours", "Panel", owner), refresh="refresh", preview="refresh", apply="apply", apply_label="Add different colours"),
    )
    return assemble("Glyph Labels", routes, preview="tglyph", parent=parent, font=font, package=package, tab=tab)
