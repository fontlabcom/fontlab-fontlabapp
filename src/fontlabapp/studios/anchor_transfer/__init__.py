# this_file: src/fontlabapp/studios/anchor_transfer/__init__.py
# SPDX-License-Identifier: Apache-2.0
"""Anchor Transfer (Phase D A13): anchor copies with a dry run before every Apply.

Launch inside FontLab with::

    from fly.ap.studios.anchor_transfer import show; show()

One ``AppShell`` window, control-less TGlyph preview on the right, five
tabs: From glyph (Copy Anchors From Glyph), Between masters (Mirror Across
Masters), Between fonts (Copy Anchors Between Fonts), From components
(Derive Anchors From Components) and CSV import (Add Anchors From File).
Each tab lists exactly the anchor edits it will write; Apply writes exactly
that plan (a font changed in between is refused as stale) as one
``Anchor Transfer: <action> <subject>`` Undo step: through
``AppShell.history`` in this font, or in the destination font for Between
fonts.
"""

from typing import Any

import fontlabapp.studios as registry
from fontlabapp.studios import TabSpec

APP = "Anchor Transfer"
TAB_TITLES = ("From glyph", "Between masters", "Between fonts", "From components", "CSV import")
#: Tab title -> (tab module, panel class).
PANELS = {
    "From glyph": ("from_glyph", "FromGlyphPanel"),
    "Between masters": ("masters", "MastersPanel"),
    "Between fonts": ("fonts", "FontsPanel"),
    "From components": ("components", "ComponentsPanel"),
    "CSV import": ("csv_import", "CsvPanel"),
}


def _builder(title: str) -> Any:
    def build(shell: Any) -> Any:
        from importlib import import_module

        from .app import tool_for

        module, name = PANELS[title]
        return getattr(import_module(f"{__name__}.{module}"), name)(tool_for(shell)).widget

    return build


def register_tabs() -> tuple[str, ...]:
    """Register each tab title not registered yet in this process; return the titles."""
    registered = {spec.title for spec in registry.tabs(APP)}
    for title in TAB_TITLES:
        if title not in registered:
            registry.register(APP, TabSpec(title, _builder(title)))
    return TAB_TITLES


def show(*args: Any, **kwargs: Any) -> Any:
    """Open Anchor Transfer for the current font; see ``app.show``."""
    from .app import show as _show

    return _show(*args, **kwargs)


def tool_for(shell: Any) -> Any:
    """The shared ``studios._kerning.Tool`` of ``shell``, created on first use."""
    from .app import tool_for as _tool_for

    return _tool_for(shell)


__all__ = ["APP", "PANELS", "TAB_TITLES", "register_tabs", "show", "tool_for"]
