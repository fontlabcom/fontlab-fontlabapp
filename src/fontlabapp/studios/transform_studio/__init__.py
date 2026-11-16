# this_file: src/fontlabapp/studios/transform_studio/__init__.py
# SPDX-License-Identifier: Apache-2.0
"""Transform Studio (Phase D A6): transform, slant and rotate or reflect outlines.

Launch inside FontLab with::

    from fly.ap.studios.transform_studio import show; show()

One ``AppShell`` window with a TGlyph preview on the right and three tabs. It
replaces the Scriptmix ``Scripts/Contours`` tools Transform, Slant, Smart Slant,
Rotate Selection, Reflect Horizontally and Reflect Vertically. Preview draws the
planned outline as a ghost and writes nothing. Apply writes explicit layers of
the preview master (or every master) as one ``"Transform Studio: …"`` Undo step
through ``AppShell.history`` and reads them back.
"""

from typing import Any

from fontlabapp.studios import TabSpec, register, tabs

APP = "Transform Studio"
TAB_TITLES = ("Transform", "Slant", "Rotate & reflect")


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
    """Open Transform Studio for the current font; see ``app.show``."""
    from .app import show as _show

    return _show(*args, **kwargs)


def studio_for(shell: Any) -> Any:
    """The ``Studio`` state of ``shell``, created on first use."""
    from .app import studio_for as _studio_for

    return _studio_for(shell)


__all__ = ["APP", "TAB_TITLES", "show", "studio_for"]
