# this_file: src/fontlabapp/studios/vertical_metrics/__init__.py
# SPDX-License-Identifier: Apache-2.0
"""Vertical Metrics & Zones (Phase D A12): master metrics, zones and the italic angle, with a dry run before every Apply.

Launch inside FontLab with::

    from fly.ap.studios.vertical_metrics import show; show()

One ``AppShell`` window, read-only TMetrics on top, five tabs: Metrics table
(Master Metrics Table), Calculate (Calculate Vertical Metrics; Vertical
Metrics Reporter), Zones (Alignment Zones; Suggest Zones From Overshoots),
Italic angle (Italic Angle) and Diagram (Vertical Metrics Diagram; Nodes Near
Zones). The Diagram tab and the Reporter only read. Each edit tab lists
exactly the master values it will change; Apply writes exactly that list (a
source changed in between is refused as stale) as one
``Vertical Metrics: <action> of <masters>`` Undo step. These are master and
font-info values, not glyph layers, so ``AppShell.history`` (glyph layers
only) cannot wrap them: each Apply goes through the existing route-A writer
of its original with the app's label (see ``_shared``).
"""

from typing import Any

import fontlabapp.studios as registry
from fontlabapp.studios import TabSpec

APP = "Vertical Metrics & Zones"
#: The Undo label prefix (Issue 242 controller note).
LABEL = "Vertical Metrics"
TAB_TITLES = ("Metrics table", "Calculate", "Zones", "Italic angle", "Diagram")
#: Tab title -> (tab module, panel class).
PANELS = {
    "Metrics table": ("table", "MetricsTablePanel"),
    "Calculate": ("calculate", "CalculatePanel"),
    "Zones": ("zones", "ZonesPanel"),
    "Italic angle": ("angle", "AnglePanel"),
    "Diagram": ("diagram", "DiagramPanel"),
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
    """Open Vertical Metrics & Zones for the current font; see ``app.show``."""
    from .app import show as _show

    return _show(*args, **kwargs)


def tool_for(shell: Any) -> Any:
    """The shared ``studios._kerning.Tool`` of ``shell``, created on first use."""
    from .app import tool_for as _tool_for

    return _tool_for(shell)


__all__ = ["APP", "LABEL", "PANELS", "TAB_TITLES", "register_tabs", "show", "tool_for"]
