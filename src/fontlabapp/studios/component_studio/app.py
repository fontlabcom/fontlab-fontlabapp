# this_file: src/fontlabapp/studios/component_studio/app.py
# SPDX-License-Identifier: Apache-2.0
"""Component Studio window assembly: shell, shared ``Tool`` state and the TGlyph preview."""

from typing import Any

import fontlabapp.fontui as fontui
from fontlabapp.studios import tabs

from .._kerning import Tool
from . import APP, register_tabs

ATTRIBUTE = "component_studio_tool"


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
    """Open Component Studio for the current font; return the shell.

    ``package``/``font`` are getters and ``preview`` a factory ``(shell, tool)``
    (tests inject them); by default the live package, Fontport font and an
    embedded control-less TGlyph are used.
    """
    shell = fontui.app_shell(APP, "tglyph", parent=parent, package=package)
    try:
        tool = Tool(shell, APP, font=font)
        setattr(shell, ATTRIBUTE, tool)
        tool.preview = (preview or glyph_preview)(shell, tool)
        if tool.preview is not None:
            shell.set_preview(tool.preview)
        register_tabs()
        for spec in tabs(APP):
            shell.add_tab(spec)
        tool.reload()
        shell.show()
    except BaseException:
        shell.close()
        raise
    return shell


def glyph_preview(shell: Any, tool: Tool) -> Any:
    """A control-less TGlyph of the current font, or None without a font."""
    font = tool.font()
    if font is None:
        return None
    package = shell.package()
    layer = str(package.master) if package is not None else None
    return fontui.glyph_view(font, shell.widget, layer=layer, controls=False, label_prefix=APP,
                             hint_check=shell.hint_check)  # fmt: skip


__all__ = ["ATTRIBUTE", "glyph_preview", "show", "tool_for"]
