# this_file: src/fontlabapp/studios/anchor_component_inspector/__init__.py
# SPDX-License-Identifier: Apache-2.0
"""Open the retained anchor/component composition through the public UI API."""

from typing import Any


def show(font: Any, parent: Any = None) -> Any:
    """Show the captured font's read-only anchor/component inspector."""
    import fontlabapp.fontui as fontui

    return fontui.anchor_component_studio(font, parent)
