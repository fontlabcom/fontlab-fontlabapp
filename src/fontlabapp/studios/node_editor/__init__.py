# this_file: src/fontlabapp/studios/node_editor/__init__.py
# SPDX-License-Identifier: Apache-2.0
"""Node Editor: per-glyph duplication, three literal policies and live coordinates."""


def duplicate_selected_nodes(mode):
    """Keep the three original immediate callable policies independently available."""
    import fontlabapp.fontui as fontui

    return fontui.duplicate_nodes(mode)


def show(parent=None):
    """Open the integrated Node Editor with an explicit captured font."""
    import fontlabapp.fontui as fontui

    return fontui.show_node_editor(parent=parent)
