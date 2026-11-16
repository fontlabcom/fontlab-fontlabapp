# this_file: src/fontlabapp/studios/kerning_studio/__init__.py
# SPDX-License-Identifier: Apache-2.0
"""Kerning Studio (Phase D A1): pairs from text, glyph pairs, groups and tightening.

Launch inside FontLab with::

    from fly.ap.studios.kerning_studio import show; show()

One ``AppShell`` window with a TMetrics preview on top and four tabs. It
replaces the Scriptmix scripts Pairs From Text, Pair Editor, Text Preview,
Kern To Max, Steal Kerning From Next Pair, Same Kerning Groups and Delete
Kerning Pair From All Masters. Reads cover every master; writes go to the
selected master (or every master for the grid and delete) as one
``"Kerning Studio: …"`` Undo step through ``fontui.write_kerning``.
"""

from typing import Any

from fontlabapp.studios import TabSpec, register, tabs

APP = "Kerning Studio"
TAB_TITLES = ("Text pairs", "Glyph pairs", "Groups", "Tighten")


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
    """Open Kerning Studio for the current font; see ``app.show``."""
    from .app import show as _show

    return _show(*args, **kwargs)


def studio_for(shell: Any) -> Any:
    """The ``Studio`` state of ``shell``, created on first use."""
    from .app import studio_for as _studio_for

    return _studio_for(shell)


__all__ = ["APP", "TAB_TITLES", "show", "studio_for"]
