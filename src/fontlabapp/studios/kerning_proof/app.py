# this_file: src/fontlabapp/studios/kerning_proof/app.py
# SPDX-License-Identifier: Apache-2.0
"""Captured-font AppShell assembly for the three Kerning Proof tasks."""

from typing import Any

import fontlabapp.fontui as fontui
from fontlabapp.core.scripting import current_package
from fontlabapp.studios import TabSpec
from fontlabapp.studios._kerning import Tool

from . import APP


def metrics_preview(shell: Any, tool: Tool) -> Any:
    """Proof never enables TMetrics metric or kerning writes."""
    font = tool.font()
    if font is None:
        return None
    return fontui.metrics_preview(font, shell.widget, controls=False, read_only=True,
                                  hint_check=shell.hint_check)


def show(parent: Any = None, *, package: Any = None, font: Any = None,
         preview: Any = None) -> Any:
    """Open a window bound to the package and Fontport font captured at launch."""
    from .pairs import PairsPanel
    from .tabs import SymmetryPanel, TextPanel

    source = package or current_package
    captured_package = source()
    captured_id = getattr(captured_package, "id", None)

    def target() -> Any:
        if getattr(source(), "id", None) != captured_id:
            raise ValueError("The original font is no longer current; reopen this tool.")
        return captured_package

    captured_font = (font or fontui.current_font)()
    shell = fontui.app_shell(APP, 'tmetrics', parent=parent, package=target)
    try:
        tool = Tool(shell, APP, font=lambda: captured_font)
        shell.kerning_proof = tool
        tool.reload()
        tool.preview = (preview or metrics_preview)(shell, tool)
        if tool.preview is not None:
            shell.set_preview(tool.preview)
            tool.preview.set_layer(tool.current)
        panels = {}
        for title, panel_type in (('Pairs From Text', PairsPanel), ('Text Preview', TextPanel),
                                  ('Symmetry', SymmetryPanel)):
            panel = panel_type(tool)
            panels[title] = panel
            shell.add_tab(TabSpec(title, lambda shell, panel=panel: panel.widget))
        shell.kerning_proof_tabs = panels
        shell.set_about(
            'Kerning Proof — inspect text and stage exact pair or symmetry changes.\n'
            'Refresh re-reads only the selected task. Preview Changes accepts its current controls.\n'
            'Source: https://github.com/fontlabcom/fontlab-fontlabapp\n'
            'Text tools: FontLab App contributors, Apache-2.0.\n'
            'Symmetry: independent implementation after Vassil Kateliev / Karandash Type Foundry, '
            'Science Gothic; original licence undeclared, no original body copied.'
        )
        shell.show()
    except BaseException:
        shell.close()
        raise
    return shell
