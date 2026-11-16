# this_file: src/fontlabapp/studios/derived_glyphs/__init__.py
# SPDX-License-Identifier: Apache-2.0
"""Derived Glyphs (Phase D A17): new glyphs made from glyphs the font already has.

Launch inside FontLab with::

    from fly.ap.studios.derived_glyphs import show; show()

One ``AppShell`` window, read-only TMetrics preview on top, six tabs:
Small caps (Small Caps From Capitals), Sups & subs (Superior & Inferior
Figures), Tabular figures (Tabular Figure Copies), Default figures (Set
Default Figures), Unicase (Make Lower Unicase) and Placeholders
(Placeholder Glyphs). Each tab lists its plan first and never changes the
font on open, on a control change or when a row is chosen; choosing a row
shows the source and, when it exists, the target in the preview. Apply
re-plans from the live font, refuses a plan that differs from the list on
screen, and writes through the originals' App writers
(``glyph_copies.create``, ``glyph_creation.create_glyphs`` and the
component-set writer) with ``Derived Glyphs: <action> <subject>`` as the
history title.
"""

from typing import Any

import fontlabapp.studios as registry
from fontlabapp.studios import TabSpec

APP = "Derived Glyphs"
TAB_TITLES = (
    "Small caps",
    "Sups & subs",
    "Tabular figures",
    "Default figures",
    "Unicase",
    "Placeholders",
)
#: Tab title -> (tab module, panel class).
PANELS = {
    "Small caps": ("small_caps", "SmallCapsPanel"),
    "Sups & subs": ("sups_subs", "SupsSubsPanel"),
    "Tabular figures": ("tabular", "TabularPanel"),
    "Default figures": ("default_figures", "DefaultFiguresPanel"),
    "Unicase": ("unicase", "UnicasePanel"),
    "Placeholders": ("placeholders", "PlaceholdersPanel"),
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
    """Open Derived Glyphs for the current font; see ``app.show``."""
    from .app import show as _show

    return _show(*args, **kwargs)


def tool_for(shell: Any) -> Any:
    """The shared ``studios._kerning.Tool`` of ``shell``, created on first use."""
    from .app import tool_for as _tool_for

    return _tool_for(shell)


__all__ = ["APP", "PANELS", "TAB_TITLES", "register_tabs", "show", "tool_for"]
