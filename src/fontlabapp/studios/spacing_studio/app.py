# this_file: src/fontlabapp/studios/spacing_studio/app.py
# SPDX-License-Identifier: Apache-2.0
"""Spacing Studio window assembly: shell, shared ``Studio`` state and TMetrics preview."""

from typing import Any

import fontlabapp.fontui as fontui
from fontlabapp.studios import tabs

from .._kerning import ERRORS
from . import APP
from .session import Studio
from .staged import bind, capture


def studio_for(shell: Any) -> Studio:
    """The ``Studio`` state of ``shell``, created on first use."""
    studio = getattr(shell, "spacing_studio", None)
    if studio is None:
        studio = shell.spacing_studio = Studio(shell)
    return studio


def show(parent: Any = None, *, package: Any = None, font: Any = None, preview: Any = None) -> Any:
    """Open Spacing Studio for the current font; return the shell.

    ``package``/``font`` are getters and ``preview`` a factory ``(shell, studio)``
    (tests inject them); by default the live package, Fontport font and an
    embedded control-less TMetrics are used.
    """
    shell = fontui.app_shell(APP, "tmetrics", parent=parent, package=package)
    try:
        from fontlabapp.core.scripting import current_package

        captured_package = capture(package or current_package)
        pending = object()
        captured_font = pending
        def frozen_font() -> Any:
            nonlocal captured_font
            if captured_font is pending:
                captured_package()
                candidate = (font or fontui.current_font)()
                captured_package()
                captured_font = candidate
            return captured_font
        shell._package = captured_package
        studio = shell.spacing_studio = Studio(shell, font=frozen_font)
        studio.preview_factory = lambda: (preview or _metrics_preview)(shell, studio)
        for spec in tabs(APP):
            shell.add_tab(spec)
        bind(studio)
        shell.set_about("Spacing Studio\nChoose glyphs and a master. Preview an action, review the rows, then Apply Changes.\n"
                        "Discard preview keeps the controls for a new plan. Strings and offset previews only read.\n"
                        "Source: https://github.com/fontlabcom/fontlab-fontlabapp\n"
                        "Credits: FontLab App contributors; see package NOTICE and source licences.")
        try:
            studio.reload()
        except ERRORS as error:
            studio.say(f"{APP}: {error}")
        for actions in shell._actions.values():
            actions["refresh"] = lambda: _refresh(shell, studio)
        before = len(shell.connections)
        try:
            attached = fontui.follow_history(shell, lambda: _refresh(shell, studio))
            note = "" if attached == 2 else "Automatic Undo/Redo refresh incomplete; use Refresh or Preview Changes."
        except Exception as error:  # noqa: BLE001 - keep manual refresh usable
            attached = len(shell.connections) - before
            note = f"Automatic Undo/Redo refresh incomplete; use Refresh or Preview Changes. {error}"
        shell._history_connections = attached
        if note:
            about = shell.about.text
            shell.set_about((about() if callable(about) else about) + "\n" + note)
        if studio.current and studio.preview is not None:
            studio.preview.set_layer(studio.current)
        shell.show()
    except BaseException:
        shell.close()
        raise
    return shell


def _refresh(shell: Any, studio: Studio) -> None:
    """Reread displayed targets without accepting plans or recapturing selection."""
    if shell.closed:
        return
    panels = [view.__self__ for view in studio.views]
    records = [(panel, list(panel.records)) for panel in panels]
    studio.rows = []
    for panel in panels:
        staged = getattr(panel, "staged", None)
        if staged is not None:
            staged.request = staged.accepted = None
        if getattr(panel, "offset_snapshot", None) is not None:
            panel.offset_snapshot = None
            records = [(owner, [] if owner is panel else rows) for owner, rows in records]
        panel.records = []
        if hasattr(panel, "comparison"):
            panel.comparison = []
    try:
        studio.reload(preserve=studio.master is not None)
        for panel, rows in records:
            panel.refresh_sources(rows)
        studio.say("Spacing refreshed. Controls kept; preview again before Apply or selected-layer offsets.")
    except Exception as error:  # noqa: BLE001 - contain native history callbacks
        for panel in panels:
            panel.records = []
            if hasattr(panel, "comparison"):
                panel.comparison = []
            panel.table.set_rows([])
        studio.say(f"Spacing refresh refused: {error}. Use Refresh or Preview Changes.")
    finally:
        shell._update_actions()


def _metrics_preview(shell: Any, studio: Studio) -> Any:
    font = studio.font()
    if font is None:
        return None
    preview = fontui.metrics_preview(font, shell.widget, controls=False, hint_check=shell.hint_check, read_only=True)
    preview.kerning_control.setChecked(False)
    return preview

__all__ = ["show", "studio_for"]
