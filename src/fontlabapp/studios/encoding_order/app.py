# this_file: src/fontlabapp/studios/encoding_order/app.py
# SPDX-License-Identifier: Apache-2.0
"""Encoding and Order previews all encodings and exports explicit order files."""

from typing import Any

import fontlabapp.fontui as fontui  # noqa: PLR0402 - avoid root lazy native exports


def show(parent: Any = None, *, package: Any = None, font: Any = None,
         tab: str | None = None) -> Any:
    """Open ordering, encoding insertion and Unicode coverage with a proof pane."""
    return fontui.identity_studio(
        'Encoding and Order',
        (
            fontui.identity_route('Glyph Order Preview and Export', lambda parent: fontui.identity_panel("fonts.identity_tools.encoding_order.order", "panel_type", parent, factory_type=True), refresh='refresh',
                  apply='apply', apply_label='Export Order…', glyph_column=0),
            fontui.identity_route('Paste Glyph Order Encoding', lambda parent: fontui.identity_panel("fonts.identity_tools.encoding_order.paste", "panel_type", parent, factory_type=True), refresh='read_source',
                  preview='preview_order', apply='choose_file', apply_label='Save Encoding…',
                  buttons=('preview_button',)),
            fontui.identity_route('Unicode Ranges and Codepages', lambda parent: fontui.identity_panel("fonts.identity_tools.encoding_order.ranges", "panel_type", parent, factory_type=True), refresh='refresh',
                  buttons=('apply_button',)),
        ),
        preview='tmetrics', parent=parent, package=package, font=font, tab=tab,
    )
