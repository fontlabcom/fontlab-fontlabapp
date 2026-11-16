# this_file: src/fontlabapp/studios/glyph_identity/app.py
# SPDX-License-Identifier: Apache-2.0
"""Glyph naming and Unicode tools in one captured-font studio."""


def show(*, parent: object = None, font: object = None, package: object = None,
         tab: str | None = None) -> object:
    """Open all original name/Unicode actions beside a read-only glyph preview."""
    import fontlabapp.fontui as fontui

    routes = (
        fontui.identity_route('Batch Rename', lambda parent: fontui.identity_panel('glyphs.identity_tools.glyph_identity.batch_rename', '_dialog_type', parent, factory_type=True),
              apply='apply', glyph_column=0, buttons=('reload_button', 'close_button', 'apply_button')),
        fontui.identity_route('Suffix Tool', lambda parent: fontui.identity_panel('glyphs.identity_tools.glyph_identity.suffix_tool', '_dialog_type', parent, factory_type=True),
              apply='apply', glyph_column=0, buttons=('reload_button', 'close_button', 'apply_button')),
        fontui.identity_route('Unicode From Names', lambda parent: fontui.identity_panel('glyphs.identity_tools.glyph_identity.unicode_from_names', '_dialog_type', parent, factory_type=True),
              apply='apply', glyph_column=0, buttons=('reload_button', 'close_button', 'apply_button')),
        fontui.identity_route('Duplicate Unicodes', lambda parent: fontui.identity_panel('glyphs.unicode.duplicates.ui', 'dialog_type', parent, factory_type=True),
              preview='update_actions', apply='apply', apply_label='Remove ticked assignments',
              preview_target=lambda panel: next(((name, None) for (name, _code), item in panel.items.items()
                                                  if item == panel.tree.currentItem()), None),
              preview_signals=(('tree', 'itemSelectionChanged'),),
              buttons=('reload_button', 'close_button', 'apply_button')),
    )
    return fontui.identity_studio('Glyph Identity', routes, preview='tglyph', parent=parent,
                       font=font, package=package, tab=tab)
