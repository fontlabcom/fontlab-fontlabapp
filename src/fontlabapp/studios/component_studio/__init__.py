# this_file: src/fontlabapp/studios/component_studio/__init__.py
# SPDX-License-Identifier: Apache-2.0
"""Component Studio (Phase D A15): component edits with a dry run before every Apply.

Launch inside FontLab with::

    from fly.ap.studios.component_studio import show; show()

One ``AppShell`` window, control-less TGlyph preview on the right, six
tabs: Build (Build From Recipes, with Dump Component Recipes as "Dump from
selection"), Replace (Replace Reference), Decompose (Decompose, Decompose
Named Components and Decompose Serif Components as three scopes), Offsets
(Copy Offsets Between Masters), Locations (Set Component Locations) and
Locks (Unlock Lock). Each tab lists exactly the component edits it will
write; Apply writes exactly that plan (a font changed in between is refused
as stale) as one ``Component Studio: <action> <subject>`` Undo step through
``AppShell.history``. Build keeps the original's route: missing master
layers are added in one such step, then FontLab's own builder builds each
layer (its Undo is FontLab's; see the Build tab).
"""

from typing import Any

import fontlabapp.studios as registry
from fontlabapp.studios import TabSpec

APP = "Component Studio"
TAB_TITLES = ("Build", "Replace", "Decompose", "Offsets", "Locations", "Locks")
#: Tab title -> (tab module, panel class).
PANELS = {
    "Build": ("build", "BuildPanel"),
    "Replace": ("replace", "ReplacePanel"),
    "Decompose": ("decompose", "DecomposePanel"),
    "Offsets": ("offsets", "OffsetsPanel"),
    "Locations": ("locations", "LocationsPanel"),
    "Locks": ("locks", "LocksPanel"),
}


def _builder(title: str) -> Any:
    def build(shell: Any) -> Any:
        from importlib import import_module

        from .app import tool_for

        module, name = PANELS[title]
        return getattr(import_module(f"{__name__}.{module}"), name)(
            tool_for(shell)
        ).widget

    return build


def register_tabs() -> tuple[str, ...]:
    """Register each tab title not registered yet in this process; return the titles."""
    registered = {spec.title for spec in registry.tabs(APP)}
    for title in TAB_TITLES:
        if title not in registered:
            registry.register(APP, TabSpec(title, _builder(title)))
    return TAB_TITLES


def show(*args: Any, **kwargs: Any) -> Any:
    """Open Component Studio for the current font; see ``app.show``."""
    from .app import show as _show

    return _show(*args, **kwargs)


def tool_for(shell: Any) -> Any:
    """The shared ``studios._kerning.Tool`` of ``shell``, created on first use."""
    from .app import tool_for as _tool_for

    return _tool_for(shell)


__all__ = ["APP", "PANELS", "TAB_TITLES", "register_tabs", "show", "tool_for"]
