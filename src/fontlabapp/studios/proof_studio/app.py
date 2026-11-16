# this_file: src/fontlabapp/studios/proof_studio/app.py
# SPDX-License-Identifier: Apache-2.0
"""Proof Studio window assembly: shell, shared ``Studio`` state and TMetrics preview."""

from typing import Any

import fontlabapp.fontui as fontui
from fontlabapp.studios import tabs

from . import APP, register_tabs
from .session import Studio


def studio_for(shell: Any) -> Studio:
    """The ``Studio`` state of ``shell``, created on first use."""
    studio = getattr(shell, "proof_studio", None)
    if studio is None:
        studio = shell.proof_studio = Studio(shell)
    return studio


def show(
    parent: Any = None,
    *,
    package: Any = None,
    font: Any = None,
    selection: Any = None,
    preview: Any = None,
    facts: Any = None,
    settings: Any = None,
    title: str = APP,
    tab_specs: Any = None,
) -> Any:
    """Open Proof Studio for the current font; return the shell.

    ``package``/``font``/``selection``/``facts`` are getters, ``settings`` a
    ``(organization, application)`` QSettings factory and ``preview`` a factory
    ``(shell, studio)`` (tests inject them); by default the live package,
    Fontport font, ordered layer selection and an embedded control-less,
    read-only TMetrics (no metric or kerning writes, not even Alt+arrow
    nudges) are used.
    """
    shell = fontui.app_shell(title, "tmetrics", parent=parent, package=package)
    try:
        studio = shell.proof_studio = Studio(shell, font=font, selection=selection, facts=facts, settings=settings,
                                             package=package)
        studio.preview = (preview or _metrics_preview)(shell, studio)
        if studio.preview is not None:
            shell.set_preview(studio.preview)
        if tab_specs is None:
            register_tabs()
            tab_specs = tabs(APP)
        for spec in tab_specs:
            shell.add_tab(spec)
        shell.show()
    except BaseException:
        shell.close()
        raise
    return shell


def _metrics_preview(shell: Any, studio: Studio) -> Any:
    font = studio.font()
    if font is None:
        return None
    return fontui.metrics_preview(font, shell.widget, controls=False, hint_check=shell.hint_check, read_only=True)


__all__ = ["show", "studio_for"]
