# this_file: src/fontlabapp/studios/layer_manager/__init__.py
# SPDX-License-Identifier: Apache-2.0
"""Layer Manager (Phase D A18): copy, back up, add, clean and deliver glyph layers.

Launch inside FontLab with::

    from fly.ap.studios.layer_manager import show; show()

One ``AppShell`` window, control-less TGlyph preview on the right, six
tabs: Copy between masters (Copy Layer Between Masters), Twins (Master
Twins), Backups (Duplicate Current Layer, Restore Backup Layer and Use
Layer As Master), Intermediate (Set Intermediate Layer), Clean-up (Layer
Cleanup and Empty Layers) and Deliver (Deliver Glyphs and the Examples
Copy Layers From Font). Every tab lists its plan first; choosing a row
shows that glyph and layer in the preview. Apply plans again from the
font, refuses a plan that differs from the list on screen, and writes the
listed layers as one ``Layer Manager: <action> <subject>`` Undo step
through ``AppShell.history``. Deliver creates missing glyphs with
FontLab's Add Glyph first, as the original did (one step per glyph).
"""

from typing import Any

import fontlabapp.studios as registry
from fontlabapp.studios import TabSpec

APP = "Layer Manager"
TAB_TITLES = (
    "Copy between masters",
    "Twins",
    "Backups",
    "Intermediate",
    "Clean-up",
    "Deliver",
)
#: Tab title -> (tab module, panel class).
PANELS = {
    "Copy between masters": ("copy_masters", "CopyMastersPanel"),
    "Twins": ("twins", "TwinsPanel"),
    "Backups": ("backups", "BackupsPanel"),
    "Intermediate": ("intermediate", "IntermediatePanel"),
    "Clean-up": ("cleanup", "CleanupPanel"),
    "Deliver": ("deliver", "DeliverPanel"),
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
    """Open Layer Manager for the current font; see ``app.show``."""
    from .app import show as _show

    return _show(*args, **kwargs)


def tool_for(shell: Any) -> Any:
    """The shared ``studios._kerning.Tool`` of ``shell``, created on first use."""
    from .app import tool_for as _tool_for

    return _tool_for(shell)


__all__ = ["APP", "PANELS", "TAB_TITLES", "register_tabs", "show", "tool_for"]
