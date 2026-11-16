# this_file: src/fontlabapp/studios/derived_glyphs/outline.py
# SPDX-License-Identifier: Apache-2.0
"""The six outline-derived glyph tasks in one read-only TGlyph workspace."""
from typing import Any

import fontlabapp.fontui as fontui  # noqa: PLR0402 - avoid native parent fallback
from fontlabapp.core.scripting import current_package
from fontlabapp.fontui import outline_generators_backends
from fontlabapp.studios import TabSpec

from .._kerning import Tool
from .._kerning_ui import button, get
from ..transform_studio.native import snapshot
from . import APP
from .effects import EffectsPanel
from .placeholders import PlaceholdersPanel
from .small_caps import SmallCapsPanel
from .sups_subs import SupsSubsPanel
from .tabular import TabularPanel

outline_generators = outline_generators_backends()

TITLES = ("Placeholders", "Tabular figures", "Sups & subs", "Small caps", "Shadow Copy", "Outline Effect")
PANELS = (PlaceholdersPanel, TabularPanel, SupsSubsPanel, SmallCapsPanel)


def glyph_preview(shell: Any, tool: Any) -> Any:
    """Bind the preview to the captured font and layer; disable all editing."""
    font = tool.font()
    if font is None:
        return None
    return fontui.glyph_view(font, shell.widget, layer=tool.current, controls=False,
                            label_prefix=APP, hint_check=shell.hint_check, read_only=True)


def signature(panel: Any, rows: Any = None) -> tuple:
    """Settings and exact source layers underlying the visible staged plan."""
    controls = tuple((name, get(getattr(panel, name).value)) for name in
                     ("advance", "extra", "factor", "shift", "x_scale", "y_scale")
                     if hasattr(panel, name))
    layers = tuple((master, getattr(layer, "id", id(layer)), snapshot(layer)) for row in (panel.rows if rows is None else rows)
                   for master, layer in getattr(row, "layers", ()))
    return panel.key, controls, panel.consented(), layers


def bind(shell: Any, tool: Any, panel: Any, title: str) -> None:
    """Require explicit Preview before Apply; keep drafts across tabs and Refresh."""
    captured_layer = tool.current
    def chosen(name: str, layer: Any = None) -> None:
        package = panel.live()
        if tool.preview is not None and package.findName(name) is not None:
            tool.preview.load(name, layer or captured_layer)

    panel.grid.row_selected.disconnect(panel.row_chosen)
    panel.row_chosen = panel.contain(chosen)
    panel.grid.row_selected.connect(panel.row_chosen)
    panel.refresh()
    state = {"accepted": None, "baseline": signature(panel)}
    def refresh() -> None:
        panel.facts = None
        panel.refresh()
        state["accepted"] = None
        state["baseline"] = signature(panel)
    def preview() -> None:
        state["accepted"] = None
        _, _, fresh = panel.checked_plan()
        state["accepted"] = signature(panel, fresh)
        panel.say("Preview accepted. Apply writes this plan; changing controls requires another Preview.")
    def ready() -> bool:
        _, _, fresh = panel.checked_plan()
        return state["accepted"] is not None and state["accepted"] == signature(panel, fresh) and panel.apply_button.isEnabled()
    original_apply = panel.apply
    def apply() -> None:
        if not ready():
            raise ValueError("Preview the unchanged plan before Apply.")
        state["accepted"] = None
        original_apply()
        state["baseline"] = signature(panel)
    panel.apply = apply
    panel.apply_button.hide()
    button(panel.widget, panel.layout, "Discard staged plan", refresh)
    shell.add_tab(TabSpec(title, lambda owner: panel.widget))
    shell.set_actions(panel.widget, refresh=refresh, preview=preview, apply=apply,
                      dirty=lambda: state["accepted"] is not None or signature(panel) != state["baseline"],
                      ready=ready, apply_label=panel.ACTION)


def show(parent: Any = None, *, package: Any = None, font: Any = None, preview: Any = None) -> Any:
    """Open all six S18 routes without opening secondary dialogs."""
    getter = package or current_package
    captured = getter()
    captured_id = None if captured is None else captured.id
    captured_master = "" if captured is None else str(captured.master)
    def bound_package() -> Any:
        live = getter()
        if (None if live is None else live.id) != captured_id:
            raise ValueError("The font changed. Close and reopen Derived Glyphs.")
        return live
    shell = fontui.app_shell(APP, "tglyph", parent=parent, package=bound_package)
    try:
        tool = shell.derived_glyphs_tool = Tool(shell, APP, font=font)
        tool.reload()
        tool.current = captured_master
        captured_font = tool.font()
        tool._font = lambda: captured_font
        tool.preview = (preview or glyph_preview)(shell, tool)
        if tool.preview is not None:
            shell.set_preview(tool.preview)
        panels = [factory(tool) for factory in PANELS]
        panels += [EffectsPanel(tool, mode) for mode in ("shadow", "effect")]
        for panel, title in zip(panels, TITLES):
            bind(shell, tool, panel, title)
        shell.set_about("Derived Glyphs\nPreview the selected source glyph and layer, inspect the plan, then Apply. "
                        "New glyphs use separate Add Glyph history steps; their outlines use another step. "
                        "Shadow Copy and Outline Effect edit existing outlines.\n"
                        "Sources: FontLab samples by Adam Twardoch (Apache-2.0). "
                        "https://github.com/fontlabcom/fontlab-python-scriptmix")
        shell.show()
    except BaseException as error:
        outline_generators.cleanup_failure(shell, error)
        raise
    return shell
