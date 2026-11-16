# this_file: src/fontlabapp/studios/component_audit/__init__.py
# SPDX-License-Identifier: Apache-2.0
"""Component Audit (Phase D A16): where components are, what they need, how they nest.

Launch inside FontLab with::

    from fly.ap.studios.component_audit import show; show()

One ``AppShell`` window, control-less TGlyph preview on the right, six
tabs: Composites (Components Report), Where used (Where Is It Used?),
Missing bases (Missing Component Bases), Nested (Nested Finder), Graph
(Component Graph) and Brackets (Bracket Layers and Components). Every tab
except Nested only reads: it opens no history and writes no glyph. Nested
lists the nested components first; Unnest writes exactly that list as one
``Component Audit: unnest components <subject>`` Undo step through
``AppShell.history`` and refuses a font changed in between as stale.
"""

from typing import Any

import fontlabapp.studios as registry
from fontlabapp.studios import TabSpec

APP = "Component Audit"
TAB_TITLES = (
    "Composites",
    "Where used",
    "Missing bases",
    "Nested",
    "Graph",
    "Brackets",
)
#: Tab title -> (tab module, panel class).
PANELS = {
    "Composites": ("composites", "CompositesPanel"),
    "Where used": ("where_used", "WhereUsedPanel"),
    "Missing bases": ("missing_bases", "MissingBasesPanel"),
    "Nested": ("nested", "NestedPanel"),
    "Graph": ("graph", "GraphPanel"),
    "Brackets": ("brackets", "BracketsPanel"),
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
    """Open Component Audit for the current font; see ``app.show``."""
    from .app import show as _show

    return _show(*args, **kwargs)


def tool_for(shell: Any) -> Any:
    """The shared ``studios._kerning.Tool`` of ``shell``, created on first use."""
    from .app import tool_for as _tool_for

    return _tool_for(shell)


__all__ = ["APP", "PANELS", "TAB_TITLES", "register_tabs", "show", "tool_for"]
