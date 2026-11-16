# this_file: src/fontlabapp/studios/character_consistency/app.py
# SPDX-License-Identifier: Apache-2.0
"""Case, character coverage and instance style links in one studio."""


def show(*, parent: object = None, font: object = None, package: object = None,
         tab: str | None = None) -> object:
    """Open the exact retained case/coverage/style actions with a text preview."""
    import fontlabapp.fontui as fontui

    routes = (
        fontui.identity_route('Case Pairs', lambda parent: fontui.identity_panel('glyphs.identity_tools.character_consistency.case_pairs', 'CasePairs', parent), preview='reload',
              apply='select_counterparts', glyph_column=0, apply_label='Select counterparts',
              buttons=('reload_button', 'close_button', 'select_button')),
        fontui.identity_route('Character Set Compare', lambda parent: fontui.identity_panel('glyphs.identity_tools.character_consistency.character_set_compare', 'CharsetCompare', parent),
              refresh='refresh', preview='refresh',
              buttons=('close_button',)),
        fontui.identity_route('Style Linker', lambda parent: fontui.identity_panel('glyphs.identity_tools.character_consistency.style_linker', 'panel_type', parent, factory_type=True),
              refresh='read_font', preview='read_font', apply='write_links',
              apply_label='Apply style links',
              buttons=('refresh_button', 'close_button', 'apply_button')),
    )
    return fontui.identity_studio('Character Consistency', routes, preview='tmetrics', parent=parent,
                       font=font, package=package, tab=tab)
