# this_file: src/fontlabapp/studios/align_nudge/__init__.py
# SPDX-License-Identifier: Apache-2.0
"""Align & Nudge (Phase D A24): align, distribute, nudge, overlap and simplify selected nodes.

Launch inside FontLab with::

    from fly.ap.studios.align_nudge import show; show()

One ``AppShell`` window with a TGlyph preview on the right and four tabs. It
replaces the Scriptmix ``Scripts/Contours`` tools Align And Distribute,
Interpolated Nudge, Overlap Nodes and Simplify Selected Nodes. Preview draws the
planned outline as a ghost and writes nothing. Apply writes explicit layers of
the preview master (or every master) as one ``"Align & Nudge: …"`` Undo step
through ``AppShell.history`` and reads them back. The shared reading, planning
session and tab scaffolding live in ``fontlabapp.studios.transform_studio``.
"""

from typing import Any

from fontlabapp.studios import TabSpec, register, tabs

APP = "Align & Nudge"
TAB_TITLES = ("Align & distribute", "Interpolated nudge", "Overlap nodes", "Simplify")


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
    """Open Align & Nudge for the current font; see ``app.show``."""
    from .app import show as _show

    return _show(*args, **kwargs)


def studio_for(shell: Any) -> Any:
    """The ``Studio`` state of ``shell``, created on first use."""
    from .app import studio_for as _studio_for

    return _studio_for(shell)


__all__ = ["APP", "TAB_TITLES", "show", "studio_for"]
