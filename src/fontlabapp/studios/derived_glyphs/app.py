# this_file: src/fontlabapp/studios/derived_glyphs/app.py
# SPDX-License-Identifier: Apache-2.0
"""Derived Glyphs window assembly: shell, shared ``Tool`` state and the read-only TMetrics preview."""

from typing import Any

import fontlabapp.fontui as fontui
from fontlabapp.studios import tabs

from .._kerning import Tool
from . import APP, register_tabs

ATTRIBUTE = "derived_glyphs_tool"


def tool_for(shell: Any) -> Tool:
    """The ``Tool`` of ``shell``, created on first use."""
    tool = getattr(shell, ATTRIBUTE, None)
    if tool is None:
        tool = Tool(shell, APP)
        setattr(shell, ATTRIBUTE, tool)
    return tool


def show(
    parent: Any = None, *, package: Any = None, font: Any = None, preview: Any = None
) -> Any:
    """Open Derived Glyphs for the current font; return the shell.

    ``package``/``font`` are getters and ``preview`` a factory ``(shell, tool)``
    (tests inject them); by default the live package, Fontport font and an
    embedded control-less, read-only TMetrics are used.
    """
    shell = fontui.app_shell(APP, "tmetrics", parent=parent, package=package)
    try:
        tool = Tool(shell, APP, font=font)
        setattr(shell, ATTRIBUTE, tool)
        tool.preview = (preview or metrics_preview)(shell, tool)
        if tool.preview is not None:
            shell.set_preview(tool.preview)
        register_tabs()
        for spec in tabs(APP):
            shell.add_tab(spec)
        tool.reload()
        if tool.current and tool.preview is not None:
            tool.preview.set_layer(tool.current)
        shell.show()
    except BaseException:
        shell.close()
        raise
    return shell


def metrics_preview(shell: Any, tool: Tool) -> Any:
    """A control-less read-only TMetrics of the current font, or None without a font."""
    font = tool.font()
    if font is None:
        return None
    return fontui.metrics_preview(font, shell.widget, controls=False, label_prefix=APP,
                                  hint_check=shell.hint_check, read_only=True)  # fmt: skip


__all__ = ["ATTRIBUTE", "metrics_preview", "show", "tool_for"]
