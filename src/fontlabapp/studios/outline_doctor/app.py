# this_file: src/fontlabapp/studios/outline_doctor/app.py
# SPDX-License-Identifier: Apache-2.0
"""Outline Doctor window assembly: shell, shared ``Studio`` state and TGlyph preview."""

from typing import Any

import fontlabapp.fontui as fontui
from fontlabapp.studios import tabs

from . import APP
from .session import Doctor


def studio_for(shell: Any) -> Doctor:
    """The ``Studio`` state of ``shell``, created on first use."""
    studio = getattr(shell, "outline_doctor", None)
    if studio is None:
        studio = shell.outline_doctor = Doctor(shell)
    return studio


def show(
    parent: Any = None, *, package: Any = None, font: Any = None, preview: Any = None
) -> Any:
    """Open Outline Doctor for the current font; return the shell.

    ``package``/``font`` are getters and ``preview`` a factory ``(shell, studio)``
    (tests inject them); by default the live package, Fontport font and an
    embedded control-less TGlyph are used.
    """
    shell = fontui.app_shell(APP, "tglyph", parent=parent, package=package)
    try:
        studio = shell.outline_doctor = Doctor(shell, font=font)
        studio.preview = (preview or _glyph_preview)(shell, studio)
        if studio.preview is not None:
            shell.set_preview(studio.preview)
        for spec in tabs(APP):
            shell.add_tab(spec)
        studio.reload()
        shell.show()
    except BaseException:
        shell.close()
        raise
    return shell


def _glyph_preview(shell: Any, studio: Doctor) -> Any:
    font = studio.font()
    if font is None:
        return None
    return fontui.glyph_view(font, shell.widget, layer=studio.current, controls=False,
                             label_prefix=APP, hint_check=shell.hint_check)  # fmt: skip


__all__ = ["show", "studio_for"]
