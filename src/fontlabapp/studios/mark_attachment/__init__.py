# this_file: src/fontlabapp/studios/mark_attachment/__init__.py
# SPDX-License-Identifier: Apache-2.0
"""Mark Attachment (Phase D A14): preview base/mark attachment, align components by anchor, add cursive anchors.

Launch inside FontLab with::

    from fly.ap.studios.mark_attachment import show; show()

One ``AppShell`` window, read-only TMetrics on top, three tabs: Mark preview
(Mark Attachment Preview, read only), Align by anchor (Align By Anchor) and
Cursive (Auto Cursive Attachment Get Sample and Add Anchors). Align and Add
list exactly the layers and values they will change; Apply writes exactly
that list (a font changed in between is refused as stale) through
``AppShell.history`` as one ``Mark Attachment: <action> <subject>`` Undo
step. "Get sample" writes only its new sample file.
"""

from typing import Any

import fontlabapp.studios as registry
from fontlabapp.studios import TabSpec

APP = "Mark Attachment"
TAB_TITLES = ("Mark preview", "Align by anchor", "Cursive")
#: Tab title -> (tab module, panel class).
PANELS = {
    "Mark preview": ("preview", "MarkPreviewPanel"),
    "Align by anchor": ("align", "AlignPanel"),
    "Cursive": ("cursive", "CursivePanel"),
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
    """Open Mark Attachment for the current font; see ``app.show``."""
    from .app import show as _show

    return _show(*args, **kwargs)


def tool_for(shell: Any) -> Any:
    """The shared ``studios._kerning.Tool`` of ``shell``, created on first use."""
    from .app import tool_for as _tool_for

    return _tool_for(shell)


__all__ = ["APP", "PANELS", "TAB_TITLES", "register_tabs", "show", "tool_for"]
