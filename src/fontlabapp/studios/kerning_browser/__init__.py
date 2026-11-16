# this_file: src/fontlabapp/studios/kerning_browser/__init__.py
# SPDX-License-Identifier: Apache-2.0
"""Kerning Browser (Phase D A9): browse and audit a font's kerning with a TMetrics preview.

Launch inside FontLab with::

    from fly.ap.studios.kerning_browser import show; show()

One ``AppShell`` window, read-only TMetrics on top, six tabs: Pairs (Pair
List Browser), Classes (Classes Browser), Exceptions (Exceptions Finder),
Missing (Missing Pairs), Masters (Compare Masters) and Energy (Kerning
Energy Report). Choosing a pair previews it on its master. Read-only except
Exceptions, whose "Remove ticked" deletes exactly the ticked exceptions as
one ``Kerning Browser: Remove <n> exceptions`` Undo step.
"""

from typing import Any

import fontlabapp.studios as registry
from fontlabapp.studios import TabSpec

APP = "Kerning Browser"
TAB_TITLES = ("Pairs", "Classes", "Exceptions", "Missing", "Masters", "Energy")
#: Tab title -> (tab module, panel class).
PANELS = {
    "Pairs": ("pairs", "PairsPanel"),
    "Classes": ("classes", "ClassesPanel"),
    "Exceptions": ("exceptions", "ExceptionsPanel"),
    "Missing": ("missing", "MissingPanel"),
    "Masters": ("masters", "MastersPanel"),
    "Energy": ("energy", "EnergyPanel"),
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
    """Open Kerning Browser for the current font; see ``app.show``."""
    from .app import show as _show

    return _show(*args, **kwargs)


def tool_for(shell: Any) -> Any:
    """The shared ``studios._kerning.Tool`` of ``shell``, created on first use."""
    from .app import tool_for as _tool_for

    return _tool_for(shell)


__all__ = ["APP", "PANELS", "TAB_TITLES", "register_tabs", "show", "tool_for"]
