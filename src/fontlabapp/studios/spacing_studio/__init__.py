# this_file: src/fontlabapp/studios/spacing_studio/__init__.py
# SPDX-License-Identifier: Apache-2.0
"""Spacing Studio (Phase D A2): sidebearings, reference copies, italic spacing and strings.

Launch inside FontLab with::

    from fly.ap.studios.spacing_studio import show; show()

One ``AppShell`` window with a TMetrics preview on top and four tabs. It
replaces the Scriptmix scripts Metrics Tuner, Equalize Sidebearings, Centre
Glyph, Copy Metrics From Reference, Sync Sidebearings, Italic Spacing, Spacing
String Preview, TMetrics Window, Layer Metric Comparison and Sidebearing Offset
Preview. Writes go to explicit layers of the selected master (or every master)
as one ``"Spacing Studio: …"`` Undo step through ``AppShell.history``; bases
move before composites and a composite whose base moves is left alone.
"""

from typing import Any

from fontlabapp.studios import TabSpec, register, tabs

APP = "Spacing Studio"
TAB_TITLES = ("Sidebearings", "Reference", "Italic", "Strings")


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
    """Open Spacing Studio for the current font; see ``app.show``."""
    from .app import show as _show

    return _show(*args, **kwargs)


def studio_for(shell: Any) -> Any:
    """The ``Studio`` state of ``shell``, created on first use."""
    from .app import studio_for as _studio_for

    return _studio_for(shell)


__all__ = ["APP", "TAB_TITLES", "show", "studio_for"]
