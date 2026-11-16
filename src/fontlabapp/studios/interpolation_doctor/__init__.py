# this_file: src/fontlabapp/studios/interpolation_doctor/__init__.py
# SPDX-License-Identifier: Apache-2.0
"""Interpolation Doctor (Phase D A5): check, count, preview and make masters compatible.

Launch inside FontLab with::

    from fly.ap.studios.interpolation_doctor import show; show()

One ``AppShell`` window with a TGlyph preview on the right and four tabs:
Check (Masters, Anchors and Components compatibility, Why You Not
Compatible, Master Node Compatibility Report), Fix (Make Compatible), Node
counts (Node Statistics, Point Counter, Point Counter (Master Layers)) and
Preview (Interpolation Preview). It replaces ten Scriptmix scripts. Check,
Node counts and Preview read only and never open a history step; Preview
ghosts the blend of two masters (or the second master) over TGlyph through
``set_overlay``. Make Compatible writes explicit layers as one
``"Interpolation Doctor: Make compatible <glyph>"`` Undo step through
``AppShell.history``. Hinted layers are refused unless you tick Edit hinted
layers anyway or remove their PostScript hints first.
"""

from typing import Any

from fontlabapp.studios import TabSpec, register, tabs

APP = "Interpolation Doctor"
TAB_TITLES = ("Check", "Fix", "Node counts", "Preview")


def _builder(index: int) -> Any:
    def build(shell: Any) -> Any:
        from .app import studio_for
        from .tabs import TAB_CLASSES

        return TAB_CLASSES[index][1](studio_for(shell)).widget

    return build


if not tabs(APP):  # one registration per process, even when this package is reloaded
    for _index, _title in enumerate(TAB_TITLES):
        register(APP, TabSpec(_title, _builder(_index)))


def show(*args: Any, **kwargs: Any) -> Any:
    """Open the Interpolation Doctor for the current font; see ``app.show``."""
    from .app import show as _show

    return _show(*args, **kwargs)


def studio_for(shell: Any) -> Any:
    """The ``Doctor`` session of ``shell``, created on first use."""
    from .app import studio_for as _studio_for

    return _studio_for(shell)


__all__ = ["APP", "TAB_TITLES", "show", "studio_for"]
