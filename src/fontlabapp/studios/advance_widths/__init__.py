# this_file: src/fontlabapp/studios/advance_widths/__init__.py
# SPDX-License-Identifier: Apache-2.0
"""Advance Widths (Phase D A11): advance-width reports and edits with a dry run before every Apply.

Launch inside FontLab with::

    from fly.ap.studios.advance_widths import show; show()

One ``AppShell`` window, read-only TMetrics on top, five tabs: Table (Width
Table), Round & scale (Round Advances, Scale Advances), Tabular (Tabular
Width, Check Tabular Widths), Marks (Zero-Width Marks) and Chart (Width
Chart). Table, Chart and Check Tabular only read. Each edit tab lists exactly
the layers it will change; Apply writes exactly that set (a layer changed in
between is refused as stale) as one ``Advance Widths: <action> <subject>``
Undo step through ``AppShell.history``.
"""

from typing import Any

import fontlabapp.studios as registry
from fontlabapp.studios import TabSpec

APP = "Advance Widths"
TAB_TITLES = ("Table", "Round & scale", "Tabular", "Marks", "Chart")
#: Tab title -> (tab module, panel class).
PANELS = {
    "Table": ("table", "TablePanel"),
    "Round & scale": ("rounding", "RoundScalePanel"),
    "Tabular": ("tabular", "TabularPanel"),
    "Marks": ("marks", "MarksPanel"),
    "Chart": ("chart", "ChartPanel"),
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
    """Open Advance Widths for the current font; see ``app.show``."""
    from .app import show as _show

    return _show(*args, **kwargs)


def tool_for(shell: Any) -> Any:
    """The shared ``studios._kerning.Tool`` of ``shell``, created on first use."""
    from .app import tool_for as _tool_for

    return _tool_for(shell)


__all__ = ["APP", "PANELS", "TAB_TITLES", "register_tabs", "show", "tool_for"]
