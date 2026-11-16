# this_file: src/fontlabapp/studios/kerning_batch/__init__.py
# SPDX-License-Identifier: Apache-2.0
"""Kerning Batch (Phase D A10): whole-table kerning edits with a dry run before every Apply.

Launch inside FontLab with::

    from fly.ap.studios.kerning_batch import show; show()

One ``AppShell`` window, read-only TMetrics on top, six tabs: Round (Round
Values), Scale (Scale Values), Remove small (Remove Small Pairs), Clamp
(Kerning Cutoff), Copy masters (Copy Between Masters) and Punctuation
(Unbundle Punctuation Kerning). Each tab lists exactly the pairs it will
change with a count; Apply writes exactly that set from the same kerning
snapshot (an outside edit in between is refused as stale) as one
``Kerning Batch: <action> <subject>`` Undo step through ``fontui.write_kerning``.
"""

from typing import Any

import fontlabapp.studios as registry
from fontlabapp.studios import TabSpec

APP = "Kerning Batch"
TAB_TITLES = ("Round", "Scale", "Remove small", "Clamp", "Copy masters", "Punctuation")
#: Tab title -> (tab module, panel class).
PANELS = {
    "Round": ("rounding", "RoundPanel"),
    "Scale": ("scale", "ScalePanel"),
    "Remove small": ("remove_small", "RemoveSmallPanel"),
    "Clamp": ("clamp", "ClampPanel"),
    "Copy masters": ("copy_masters", "CopyPanel"),
    "Punctuation": ("punctuation", "PunctuationPanel"),
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
    """Open Kerning Batch for the current font; see ``app.show``."""
    from .app import show as _show

    return _show(*args, **kwargs)


def tool_for(shell: Any) -> Any:
    """The shared ``studios._kerning.Tool`` of ``shell``, created on first use."""
    from .app import tool_for as _tool_for

    return _tool_for(shell)


__all__ = ["APP", "PANELS", "TAB_TITLES", "register_tabs", "show", "tool_for"]
