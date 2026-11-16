# this_file: src/fontlabapp/studios/derived_glyphs/effects.py
# SPDX-License-Identifier: Apache-2.0
"""Shadow and hollow-outline tabs, using the original guarded writers."""
from importlib import import_module
from typing import Any

from fontlabapp.fontui import outline_generators_backends

from .._kerning_ui import combo, get, spin
from .._kerning_ui import row as form_row
from ..transform_studio.native import snapshot
from ._shared import PlanPanel, plural

outline_generators = outline_generators_backends()



class EffectsPanel(PlanPanel):
    """Stage the selected layers and settings before an explicit write."""

    HEADERS = ("Glyph", "Contours / action")
    CONSENT = outline_generators.selection_panel.BASES_TEXT

    def __init__(self, tool: Any, mode: str) -> None:
        if mode not in ("shadow", "effect"):
            raise ValueError("Unknown outline effect")
        self.mode = mode
        self.model = import_module(f"{__package__}.{mode}")
        self.ACTION = "Add Shadow" if mode == "shadow" else "Outline"
        super().__init__(tool)

    def build_controls(self, form: Any) -> None:
        self.controls = []
        settings = (("Offset x", -1000, 1000, 40), ("Offset y", -1000, 1000, -40)) if self.mode == "shadow" else (("Line width", 2, 400, 30),)
        for title, low, high, value in settings:
            control = spin(self.widget, low, high, value, suffix=" units", slot=self.contain(self.refresh))
            form_row(self.widget, form, title, control)
            self.controls.append(control)
        self.scope = combo(self.widget, ["Current master", "All masters"], self.contain(self.refresh))
        form_row(self.widget, form, "Masters", self.scope)

    def settings(self) -> tuple[int, ...]:
        return tuple(int(get(control.value)) for control in self.controls)

    def plan(self, package: Any, facts: Any) -> list[Any]:
        masters = self.masters if get(self.scope.currentIndex) else [self.tool.current]
        return self.model.survey(package, self.names or [], masters, facts, self.consented())

    def plan_key(self, package: Any, rows: list[Any]) -> Any:
        return (package.id, self.settings(), tuple(
            (row.glyph.name, row.master, row.note, getattr(row.layer, "id", id(row.layer)), snapshot(row.layer) if row.layer is not None else None)
            for row in rows
        ))

    def cells(self, row: Any) -> tuple:
        return row.glyph.name, row.master, (row.note or row.contours,)

    def row_name(self, row: Any) -> str:
        return row.glyph.name

    def preview_names(self, row: Any) -> list[str]:
        return []

    def write(self, package: Any, rows: list[Any], facts: Any) -> dict:
        action = self.model.add_shadows if self.mode == "shadow" else self.model.outline
        return action(rows, *self.settings(), facts, self.consented())

    def result_text(self, result: dict) -> str:
        if not result["layers"]:
            return "Nothing changed"
        return f"Changed {plural(result['layers'], 'layer')} in {plural(result['glyphs'], 'glyph')}"
