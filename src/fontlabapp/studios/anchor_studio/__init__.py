# this_file: src/fontlabapp/studios/anchor_studio/__init__.py
# SPDX-License-Identifier: Apache-2.0
"""Anchor Studio (Phase D A3): place, align, rename, clean up and inspect anchors.

Launch inside FontLab with::

    from fly.ap.studios.anchor_studio import show; show()

One ``AppShell`` window with a TGlyph preview on the right and five tabs. It
replaces the Scriptmix ``Scripts/Anchors`` tools Place From Bounds, Center
Horizontally, Optical Center, Snap To Metrics, Round To Grid, Rename Bulk,
Delete By Name, Duplicates Finder, Remove Extraneous Mark Anchors, Cloud View
and Duplicate Anchor Rings. Writes go to explicit layers of the preview master
(or every master) as one ``"Anchor Studio: …"`` Undo step through
``AppShell.history`` and are read back; the Overlays tab only reads.
"""

from typing import Any

from fontlabapp.studios import TabSpec, register, tabs

APP = "Anchor Studio"
TAB_TITLES = ("Place", "Align", "Rename & delete", "Clean-up", "Overlays")


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
    """Open Anchor Studio for the current font; see ``app.show``."""
    from .app import show as _show

    return _show(*args, **kwargs)


def studio_for(shell: Any) -> Any:
    """The ``Studio`` state of ``shell``, created on first use."""
    from .app import studio_for as _studio_for

    return _studio_for(shell)


__all__ = ["APP", "TAB_TITLES", "show", "studio_for"]
