# this_file: src/fontlabapp/studios/kerning_studio/app.py
# SPDX-License-Identifier: Apache-2.0
"""Kerning Studio window assembly: shell, shared ``Studio`` state and TMetrics preview."""

from typing import Any

import fontlabapp.fontui as fontui
from fontlabapp.core.scripting import current_package
from fontlabapp.studios import tabs

from . import APP
from .session import Studio


def studio_for(shell: Any) -> Studio:
    """The ``Studio`` state of ``shell``, created on first use."""
    studio = getattr(shell, "kerning_studio", None)
    if studio is None:
        studio = shell.kerning_studio = Studio(shell)
    return studio


def show(parent: Any = None, *, package: Any = None, font: Any = None, preview: Any = None, consolidated: bool = False) -> Any:
    """Open Kerning Studio for the current font; return the shell.

    ``package``/``font`` are getters and ``preview`` a factory ``(shell, studio)``
    (tests inject them); by default the live package, Fontport font and an
    embedded control-less TMetrics are used.
    """
    shell = fontui.app_shell(APP, "tmetrics", parent=parent, package=package)
    try:
        from fontlabapp.studios._kerning_app import capture_source
        from .staged import StagedStudio

        bound = capture_source(package or current_package)
        captured_font = (font or fontui.current_font)()
        shell._package = bound
        studio = shell.kerning_studio = (StagedStudio if consolidated else Studio)(shell, font=lambda: captured_font)
        studio.preview = (preview or _metrics_preview)(shell, studio)
        if studio.preview is not None:
            shell.set_preview(studio.preview)
        for spec in tabs(APP):
            if not consolidated or spec.title in ("Glyph pairs", "Tighten"):
                shell.add_tab(spec)
        if consolidated:
            from fontlabapp.studios import TabSpec, _kerning_app
            from fontlabapp.studios.kerning_batch.punctuation import PunctuationPanel
            from .pairs import PairEditorPanel
            from .current_pair import CurrentPairPanel
            from .selected_delete import DeletePanel
            from .selected_steal import StealPanel

            tool = _kerning_app.tool_for(shell, APP)
            tool._font = lambda: captured_font
            tool.preview = studio.preview
            shell.add_tab(TabSpec("Kern To Max", lambda owner: CurrentPairPanel(tool).widget))
            shell.add_tab(TabSpec("Delete selected pairs", lambda owner: DeletePanel(tool).widget))
            shell.add_tab(TabSpec("Steal next pair", lambda owner: StealPanel(tool).widget))
            shell.add_tab(TabSpec("Pair Editor", lambda owner: PairEditorPanel(tool).widget))
            shell.add_tab(TabSpec("Punctuation", lambda owner: PunctuationPanel(tool).widget))
            _kerning_app.bind_actions(shell, tool)
            tool.reload()
        for view in studio.views:
            panel = view.__self__
            if consolidated:
                from fontlabapp.studios.spacing_studio.staged import buttons
                from fontlabapp.studios._kerning_ui import button

                for control in buttons(panel.layout):
                    text = control.text() if callable(control.text) else control.text
                    if text.startswith(("Set ", "Nudge ", "Kern To", "Delete ", "Apply matched")):
                        control.setText("Stage " + text)
                button(panel.widget, panel.layout, "Discard staged action", studio.discard)
                shell.set_actions(panel.widget, refresh=studio.reload, preview=studio.preview_changes,
                                  apply=studio.apply_changes, ready=studio.ready, dirty=lambda: studio.accepted is not None)
            else:
                shell.set_actions(panel.widget, refresh=studio.reload, preview=panel.refresh)
        shell.set_about("Kerning Studio\nChoose a glyph pair and master before using the named editing actions. "
                        "Blank master values delete records; zero is an explicit value.\n"
                        "Source: https://github.com/fontlabcom/fontlab-fontlabapp\n"
                        "Credits: FontLab App contributors. Alex Slobzheninov: Kern To Max, Delete Pair, Steal Kerning (Apache-2.0).\n"
                        "https://github.com/slobzheninov/Glyphs-Scripts\n"
                        "Punctuation: independent MIT rewrite after Simon Cozens. https://github.com/simoncozens/GlyphsScripts")
        studio.reload()
        for actions in shell._actions.values():
            actions["refresh"] = lambda: _refresh(shell, studio)
        before = len(shell.connections)
        try:
            attached = fontui.follow_history(shell, lambda: _refresh(shell, studio))
            note = "" if attached == 2 else "Automatic Undo/Redo refresh incomplete; use Refresh, or Preview Changes for staged pairs."
        except Exception as error:  # noqa: BLE001 - preserve a usable manual Refresh
            attached = len(shell.connections) - before
            note = f"Automatic Undo/Redo refresh incomplete; use Refresh, or Preview Changes for staged pairs. {error}"
        shell._history_connections = attached
        if note:
            about = shell.about.text
            shell.set_about((about() if callable(about) else about) + "\n" + note)
            if studio.snapshot is not None:
                shell.set_status(note)
        if studio.current and studio.preview is not None:
            studio.preview.set_layer(studio.current)
        shell.show()
    except BaseException:
        shell.close()
        raise
    return shell


def _refresh(shell: Any, studio: Studio) -> None:
    """Follow history on the captured target; never write or recapture selection."""
    if shell.closed:
        return
    tool = getattr(shell, "kerning_tool", None)
    if hasattr(studio, "accepted"):
        studio.accepted = None
    try:
        if tool is not None:
            from .pairs import PairEditorPanel

            for view in tool.views:
                panel = view.__self__
                if isinstance(panel, PairEditorPanel):
                    panel.invalidate_history()
        if not studio.reload(preserve=True):
            raise ValueError(studio.status)
        if tool is not None:
            tool.package, tool.masters, tool.current = shell.package(), list(studio.masters), studio.master
            for view in tool.views:
                view.__self__.refresh()
            # A derived punctuation plan needs an explicit Preview after history.
            from fontlabapp.studios.kerning_batch.punctuation import PunctuationPanel

            for view in tool.views:
                panel = view.__self__
                if isinstance(panel, PunctuationPanel):
                    panel.snapshot, panel.edits = None, {}
                    panel.apply_button.setEnabled(False)
        refresh = getattr(studio.preview, "refresh", None)
        if callable(refresh):
            refresh()
        studio.say("Kerning refreshed. Drafts kept; preview or stage actions again before Apply.")
    except Exception as error:  # noqa: BLE001 - never escape a native history callback
        studio.snapshot = None
        if tool is not None:
            tool.package = None
            for view in tool.views:
                panel = view.__self__
                if isinstance(panel, PairEditorPanel):
                    panel.invalidate_history()
                else:
                    try:
                        view()
                    except Exception:
                        pass  # keep the original refresh failure visible
        studio.say(f"Kerning refresh refused: {error}. Use Refresh, or Preview Changes for staged pairs.")


def _metrics_preview(shell: Any, studio: Studio) -> Any:
    font = studio.font()
    if font is None:
        return None
    return fontui.metrics_preview(font, shell.widget, controls=False, hint_check=shell.hint_check, read_only=True)



__all__ = ["show", "studio_for"]
