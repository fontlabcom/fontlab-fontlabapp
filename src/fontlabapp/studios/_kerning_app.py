# this_file: src/fontlabapp/studios/_kerning_app.py
# SPDX-License-Identifier: Apache-2.0
"""Window assembly shared by Kerning Browser and Kerning Batch: one ``AppShell``, one ``Tool``, TMetrics on top.

What: ``show`` opens the shell (``fontui.app_shell(app, "tmetrics")``), keeps
one ``studios._kerning.Tool`` on it, embeds a control-less read-only TMetrics
preview of the current font, adds every registered tab, reads the package and
shows the current master in the preview; any failure closes the shell and
re-raises. Used by ``kerning_browser.app`` and ``kerning_batch.app``.
"""

from collections.abc import Callable
from typing import Any

import fontlabapp.fontui as fontui
from fontlabapp.core.scripting import current_package
from fontlabapp.studios import tabs

from ._kerning import Tool

ATTRIBUTE = "kerning_tool"


def tool_for(shell: Any, app: str) -> Tool:
    """The ``Tool`` of ``shell``, created on first use."""
    tool = getattr(shell, ATTRIBUTE, None)
    if tool is None:
        tool = Tool(shell, app)
        setattr(shell, ATTRIBUTE, tool)
    return tool


def show(app: str, register_tabs: Callable[[], Any], *, parent: Any = None, package: Any = None,
         font: Any = None, preview: Any = None, title: str | None = None,
         tab_titles: tuple[str, ...] | None = None) -> Any:
    """Open ``app`` for the current font; return the shell."""
    shell = fontui.app_shell(title or app, "tmetrics", parent=parent, package=package)
    try:
        getter = package or current_package
        bound = capture_source(getter, deferred=True)
        pending = object()
        captured_font = pending
        def frozen_font() -> Any:
            nonlocal captured_font
            if captured_font is pending:
                bound()
                candidate = (font or fontui.current_font)()
                bound()
                captured_font = candidate
            return captured_font
        shell._package = bound
        tool = Tool(shell, app, font=frozen_font)
        setattr(shell, ATTRIBUTE, tool)
        tool.preview_factory = lambda: (preview or metrics_preview)(shell, tool)
        register_tabs()
        for spec in tabs(app):
            if tab_titles is None or spec.title in tab_titles:
                shell.add_tab(spec)
        bind_actions(shell, tool)
        shell.set_about(f"{title or app}\nChoose a task tab, review its rows, then apply its named action. "
                        "Refresh rereads the font and recalculates previews; controls are retained.\n"
                        "Source: https://github.com/fontlabcom/fontlab-fontlabapp\n"
                        "Credits: FontLab App contributors; see package NOTICE and each tab source for licences.")
        tool.reload()
        if tool.current and tool.preview is not None:
            tool.preview.set_layer(tool.current)
        shell.show()
    except BaseException:
        shell.close()
        raise
    return shell


def capture_source(getter: Callable[[], Any], *, deferred: bool = False) -> Callable[[], Any]:
    """Bind one valid font; deferred startup failures leave a recoverable shell."""
    unbound = object()
    captured = unbound if deferred else getter()
    identity = None if deferred else getattr(captured, "id", None)

    def bound() -> Any:
        nonlocal captured, identity
        current = getter()
        if captured is unbound:
            candidate_id = getattr(current, "id", None)
            if current is not None:
                tuple(getattr(current, "masters", ()))
                str(getattr(current, "master", ""))
            captured, identity = current, candidate_id
        if current is not captured and (identity is None or getattr(current, "id", None) != identity):
            raise ValueError("The original font is no longer current; reopen this tool.")
        if captured is not None and getattr(captured, "isNull", False):
            raise ValueError("The original font is closed; reopen this tool.")
        return captured

    return bound


def bind_actions(shell: Any, tool: Tool) -> None:
    """Route bottom actions to the existing tab controllers without duplicating writers."""
    for view in tool.views:
        panel = view.__self__
        if panel.widget in getattr(shell, "_actions", {}):
            continue
        apply = getattr(panel, "apply", None)
        shell.set_actions(panel.widget, refresh=tool.reload, preview=panel.refresh,
                          apply=apply, ready=getattr(panel, "ready", None),
                          apply_label=getattr(panel, "ACTION", "Apply Changes"))


def metrics_preview(shell: Any, tool: Tool) -> Any:
    """A control-less read-only TMetrics of the current font, or None without a font."""
    font = tool.font()
    if font is None:
        return None
    return fontui.metrics_preview(font, shell.widget, controls=False, hint_check=shell.hint_check, read_only=True)


__all__ = ["ATTRIBUTE", "metrics_preview", "show", "tool_for"]
