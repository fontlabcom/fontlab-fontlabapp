# this_file: src/fontlabapp/studios/font_audit/app.py
# SPDX-License-Identifier: Apache-2.0
"""Font Audit window assembly: shell, shared ``Studio`` state and read-only TMetrics preview."""

from collections.abc import Callable
from typing import Any

import fontlabapp.fontui as fontui
from fontlabapp.studios import tabs

from . import APP, register_tabs
from .session import Studio


def studio_for(shell: Any) -> Studio:
    """The ``Studio`` state of ``shell``, created on first use."""
    studio = getattr(shell, "font_audit", None)
    if studio is None:
        studio = shell.font_audit = Studio(shell)
    return studio


def show(
    parent: Any = None,
    *,
    package: Any = None,
    font: Any = None,
    preview: Any = None,
    case_metadata: Callable | None = None,
    case_preferred: Callable | None = None,
    task_specs: Any = None,
    **studio: Any,
) -> Any:
    """Open Font Audit for the current font; return the shell.

    ``case_metadata``/``case_preferred`` are the Case Coverage GlyphData
    callbacks the Scriptmix launcher supplies (App cannot import GlyphData).
    ``package``/``font`` are getters, ``preview`` a factory ``(shell, studio)``
    and ``studio`` further ``Studio`` fakes; tests inject them.
    ``task_specs`` optionally supplies the WP08 source-named report routes.
    """
    shell = fontui.app_shell(APP, "tmetrics", parent=parent, package=package)
    try:
        state = shell.font_audit = Studio(
            shell, font=font, package=package, case_metadata=case_metadata, case_preferred=case_preferred, **studio
        )
        state.preview = (preview or _metrics_preview)(shell, state)
        if state.preview is not None:
            shell.set_preview(state.preview)
        register_tabs()
        for spec in tabs(APP) if task_specs is None else task_specs:
            shell.add_tab(spec)
        state.reload()
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
