# this_file: src/fontlabapp/studios/component_audit/nested.py
# SPDX-License-Identifier: Apache-2.0
"""Nested tab: the Scriptmix "Nested Components" (Scripts/Components/Nested Finder.py).

Lists every component whose base glyph is itself a composite, on the chosen
masters of the selected glyphs or of the whole font, then unnests each by
one level: the base's inner components and own contours replace it, placed
with the outer transform, so the glyph looks the same. The original's
planner (``nested_changes``) is kept verbatim; the plan, blocked rows,
auto-layer refusal, stale check and write are Component Studio's reviewed
``ComponentPanel`` (``component_writer.EjectEditor(unlock=False)``, as the
original). "Glyphs": Selected glyphs (default) or Whole font (re-reads the
font, as the original's reload); "Masters": all masters by default, as the
original. Unnest writes the listed rows as one
``Component Audit: unnest components <subject>`` Undo step through
``AppShell.history`` on the listed layers, retaining the removed
components, then reads them back. Auto layers are listed and never edited;
a glyph that owns an auto layer or is a base of one refuses the batch (no
opt-in, as in the original).
"""

from typing import Any

import fontlabapp.core.scripting as scripting  # noqa: PLR0402 - the package __getattr__ is native

from .._kerning_ui import combo, get, row
from ..component_studio import _shared as studio_shared
from ._shared import label

#: The original's module name, read by the verbatim function below.
component_writer = studio_shared.Modules("components")


# ---------------------------------------------------------------- verbatim original
# Nested Finder
def nested_changes(
    package: Any, glyph: Any, layer: Any, master: str
) -> list[component_writer.Change]:
    """One row per component whose base glyph has components on this master."""
    rows: list[component_writer.Change] = []
    for shape in component_writer.components(layer):
        contours, inner = component_writer.part_counts(package, shape, master)
        if not inner:
            continue
        source = package.findName(component_writer.base_of(shape))
        base = component_writer.layer_of(
            source, shape.shapeData.componentLayer or master
        )
        names = (
            " + ".join(
                component_writer.base_of(s) for s in component_writer.components(base)
            )
            if base
            else ""
        )
        why = component_writer.copy_problem(
            package, (glyph.name, master), shape, master
        )
        if why:
            rows.append(
                component_writer.Change(
                    component_writer.base_of(shape), names, "", problem=why
                )
            )
            continue
        rows.append(
            component_writer.Change(
                component_writer.base_of(shape),
                names,
                component_writer.parts_text(contours, inner),
                shape.id,
            )
        )
    return rows


# ---------------------------------------------------------------- tab
class NestedPanel(studio_shared.ComponentPanel):
    """Glyph scope and master scope; one row per nested component."""

    ACTION, DONE, UNDO = "Unnest", "Unnested", "unnest components"
    HEADERS: tuple[str, ...] = ("Glyph · master", "Component", "Contains", "Becomes")
    SCOPE = 1  # every master, like the original

    def build_controls(self, form: Any) -> None:
        self.glyph_scope = combo(
            self.widget, ["Selected glyphs", "Whole font"], self.contain(self.refresh)
        )
        row(self.widget, form, "Glyphs", self.glyph_scope)
        self.scope_box(form)

    def glyph_names(self) -> list[str]:
        if get(self.glyph_scope.currentIndex) == 1:
            return [name for name, _ in scripting.names_font_glyphs()]
        return self.tool.selected_names()

    def summary(self, plan: Any) -> str:
        if not plan.rows:
            return "No nested components found"
        return super().summary(plan)

    def planner(self) -> Any:
        package = self.package
        return lambda glyph, master, layer: nested_changes(
            package, glyph, layer, master
        )

    def editor(self) -> Any:
        return component_writer.EjectEditor(unlock=False)

    def title(self, plan: Any) -> str:
        return label(self.UNDO, (glyph.name for glyph, _, _ in plan.work))


__all__ = ["NestedPanel", "nested_changes"]
