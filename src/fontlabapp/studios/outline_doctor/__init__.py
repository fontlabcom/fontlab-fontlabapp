# this_file: src/fontlabapp/studios/outline_doctor/__init__.py
# SPDX-License-Identifier: Apache-2.0
"""Outline Doctor (Phase D A4): scan and fix outline problems through one check registry.

Launch inside FontLab with::

    from fly.ap.studios.outline_doctor import show; show()

One ``AppShell`` window with a TGlyph preview on the right and five tabs:
Scan, Handles, Points, Segments and Overlaps. It replaces fourteen Scriptmix
``Scripts/Contours`` scripts (``checks.CHECKS`` lists them). Scan and Preview
read only and never open a history step; Preview draws the planned outline as
a ghost and highlights the affected points. Apply writes explicit layers as one
``"Outline Doctor: <action> <glyph>"`` Undo step through ``AppShell.history``
and reads them back. Hinted layers are refused unless you tick Edit hinted
layers anyway or remove their PostScript hints first.
"""

from typing import Any

from fontlabapp.studios import TabSpec, register, tabs

APP = "Outline Doctor"
TAB_TITLES = ("Scan", "Handles", "Points", "Segments", "Overlaps")


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
    """Open the Outline Doctor for the current font; see ``app.show``."""
    from .app import show as _show

    return _show(*args, **kwargs)


def studio_for(shell: Any) -> Any:
    """The ``Doctor`` session of ``shell``, created on first use."""
    from .app import studio_for as _studio_for

    return _studio_for(shell)


__all__ = ["APP", "TAB_TITLES", "show", "studio_for"]
