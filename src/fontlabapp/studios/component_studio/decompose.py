# this_file: src/fontlabapp/studios/component_studio/decompose.py
# SPDX-License-Identifier: Apache-2.0
"""Decompose tab (Decompose, Decompose Named Components, Decompose Serif Components).

The three originals become the three "Components" scopes of one tab; each
scope keeps its original's planner, editor, master default and texts:

- **All components** (Decompose, ``decompose_changes``): every component of
  the selected glyphs becomes the parts of its base glyph, one level per
  press (" (nested: press again)"); a base that cannot be copied is a red
  row and refuses the batch. Masters default: current master.
- **Named component** (Decompose Named Components, ``make_plan``): only
  components whose source is the exact name typed; the whole subtree is
  flattened into independent outlines. Refused glyphs, missing, automatic,
  locked or service layers and copy problems are listed as "kept: ..."
  rows and do not block the other rows. Copies are made on Apply, before
  history. Masters default: all masters.
- **Serif components** (Decompose Serif Components, ``changes``): only
  components whose base name starts with "Serif". Masters default: current
  master.

New contours are unlocked (``EjectEditor(unlock=True)``). Auto layers are
listed and kept; a glyph that owns auto layers or is a base of one is
refused (no opt-in, as in the originals). Apply writes the listed
decomposition as one ``Component Studio: decompose ... <subject>`` Undo
step and hands FontLab each removed component with its data and builder
(``retain``); Edit > Undo of removed components depends on FontLab
(fl#7641, qualified natively in T29).

Credits: Decompose Named Components is an independent behaviour rewrite
after Fernando Díaz & Reset Type Studio, Glyphs-Scripts (Apache-2.0);
Decompose Serif Components after Pedro Arilla, glyphs-scripts (Apache-2.0).
No source code was copied.
"""

from typing import Any

import fontlabapp.core.edit_guards as edit_guards  # noqa: PLR0402 - the package __getattr__ is native
import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - the package __getattr__ is native

from .._kerning_ui import combo, get, line_edit, row
from . import _shared

#: The originals' module names, read by the verbatim functions below.
component_writer = _shared.Modules("components")
writer = component_writer

SCOPES = ("All components", "Named component", "Serif components")
#: Scope -> (Undo action, the original's master default: 0 current, 1 all).
SCOPE_SETTINGS = {
    "All components": ("decompose components", 0),
    "Named component": ("decompose named components", 1),
    "Serif components": ("decompose Serif components", 0),
}


# ---------------------------------------------------------------- verbatim originals
# Decompose
def decompose_changes(
    package: Any, glyph: Any, layer: Any, master: str
) -> list[component_writer.Change]:
    """One row per component of the layer: its base and what it becomes."""
    rows: list[component_writer.Change] = []
    for shape in component_writer.components(layer):
        why = component_writer.copy_problem(
            package, (glyph.name, master), shape, master
        )
        if why:
            rows.append(
                component_writer.Change(
                    component_writer.base_of(shape), "", "", problem=why
                )
            )
            continue
        contours, inner = component_writer.part_counts(package, shape, master)
        becomes = component_writer.parts_text(contours, inner)
        if inner:
            becomes += " (nested: press again)"
        rows.append(
            component_writer.Change(
                component_writer.base_of(shape), "", becomes, shape.id
            )
        )
    return rows


# Decompose Serif Components
def changes(package: Any, glyph: Any, master: str, layer: Any) -> list[writer.Change]:
    """Describe only Serif-prefixed components; block unsafe base copies."""
    result = []
    for part in writer.components(layer):
        base = writer.base_of(part)
        if not base.startswith("Serif"):
            continue
        problem = writer.copy_problem(package, (glyph.name, master), part, master)
        result.append(
            writer.Change(base, "component", "editable parts", part.id, problem=problem)
        )
    return result


# Decompose Named Components
def flatten_parts(shape: Any, depth: int = 0) -> list[Any]:
    """Copy one subtree into detached outlines, in drawing order.

    Use the public App eject helper at every level. Its native eject applies
    placement, and its copy repair keeps flags and element metadata.
    Bound recursion even when a component cache disagrees with the preview.
    """
    if depth >= component_writer.MAX_DEPTH:
        raise ValueError("Components nest too deeply; component kept.")
    result: list[Any] = []
    for part in component_writer.eject(shape):
        if part.isComponent:
            result.extend(flatten_parts(part, depth + 1))
        else:
            result.append(part)
    return result


def source_contours(package: Any, shape: Any, master: str, depth: int = 0) -> int:
    """Count expected contours from source layers, independently of copy caches."""
    if depth >= component_writer.MAX_DEPTH:
        raise ValueError("Components nest too deeply; component kept.")
    base = package.findName(component_writer.base_of(shape))
    layer_name = str(shape.shapeData.componentLayer) or master
    layer = component_writer.layer_of(base, layer_name) if base is not None else None
    if layer is None:
        raise ValueError(f"Missing base layer {layer_name}.")
    return sum(
        source_contours(package, part, master, depth + 1)
        if part.isComponent
        else len(part.contours)
        for part in layer.shapes
    )


def checked_parts(package: Any, shape: Any, master: str) -> list[Any]:
    """Refuse detached copy loss before history can remove the occurrence."""
    expected = source_contours(package, shape, master)
    parts = flatten_parts(shape)
    if sum(len(part.contours) for part in parts) != expected:
        raise ValueError("Copied contour count differs from the source subtree.")
    return parts


class NamedEditor(component_writer.EjectEditor):
    """Prepare full subtree copies; inherit retained removal and read-back."""

    def prepare(self, layer: Any, edits: list[Any]) -> list[Any]:
        """Prepare (original component, flattened parts, placed parts)."""
        steps = []
        for shape_id, parts in edits:
            if parts is None:
                raise ValueError("Prepare component copies on Apply first.")
            shape = layer.shapes[component_writer.shape_index(layer, shape_id)]
            if self.unlock:
                for part in parts:
                    part.contentLocked = False
            steps.append((shape, parts, []))
        return steps


def make_plan(
    package: Any,
    glyphs: list[Any],
    masters: list[str],
    name: str,
    facts: history.AutoFacts,
    *,
    copy: bool = False,
) -> component_writer.Plan:
    """Read counts for preview; copy only on Apply, before history opens."""
    plan = component_writer.Plan()
    refused = history.refusals(facts, [g.name for g in glyphs], "geometry")
    for glyph in glyphs:
        for master in masters:
            label = f"{glyph.name} · {master}"
            layer = component_writer.layer_of(glyph, master)
            candidates = (
                [
                    s
                    for s in component_writer.components(layer)
                    if component_writer.base_of(s) == name
                ]
                if layer is not None
                else []
            )
            if not candidates and (
                layer is not None
                or not any(
                    component_writer.base_of(s) == name
                    for other in glyph.layers
                    for s in component_writer.components(other)
                )
            ):
                continue
            reason = refused.get(glyph.name, "")
            if layer is None:
                reason = "missing master layer"
            elif (
                layer.autoLayer
                or layer.isLocked
                or layer.isMaskLayer
                or layer.isService
            ):
                reason = "automatic, locked or service layer"
            if reason:
                plan.rows.append(
                    (label, component_writer.Change(name, "", f"kept: {reason}"))
                )
                plan.refused.append(label)
                continue
            edits = []
            for shape in candidates:
                reason = component_writer.copy_problem(
                    package, (glyph.name, master), shape, master
                )
                parts = None
                if not reason:
                    try:
                        if copy:
                            parts = checked_parts(package, shape, master)
                        else:
                            source_contours(package, shape, master)
                    except (ValueError, RuntimeError, TimeoutError) as error:
                        reason = str(error)
                row = component_writer.Change(
                    name,
                    "",
                    f"kept: {reason}" if reason else "independent outlines",
                    None if reason else (shape.id, parts),
                )
                plan.rows.append((label, row))
                if not reason:
                    edits.append((shape.id, parts))
            if edits:
                plan.work.append((glyph, layer, edits))
    return plan


# ---------------------------------------------------------------- tab
class DecomposePanel(_shared.ComponentPanel):
    """Components scope (all / named / Serif), source name for named, master scope."""

    ACTION, DONE = "Decompose", "Decomposed"
    HEADERS: tuple[str, ...] = ("Glyph · master", "Component", "Becomes")

    def build_controls(self, form: Any) -> None:
        self.kind = combo(self.widget, list(SCOPES), self.contain(self.rescope))
        row(self.widget, form, "Components", self.kind)
        self.source_edit = line_edit(
            self.widget, "", "Exact component source name", self.contain(self.replan)
        )
        row(self.widget, form, "Component", self.source_edit)
        self.scope_box(form)
        self.source_edit.setEnabled(False)

    def chosen_kind(self) -> str:
        return SCOPES[max(get(self.kind.currentIndex), 0)]

    @property
    def UNDO(self) -> str:  # noqa: N802 - the panel attribute the base reads
        return SCOPE_SETTINGS[self.chosen_kind()][0]

    @property
    def SCOPE(self) -> int:  # noqa: N802 - the panel attribute the base reads
        return SCOPE_SETTINGS[self.chosen_kind()][1]

    def rescope(self) -> None:
        """A new scope takes its original's master default and name field."""
        self.source_edit.setEnabled(self.chosen_kind() == "Named component")
        if self.scope is not None:
            self.scope.setCurrentIndex(self.SCOPE)
        self.replan()

    def named(self) -> bool:
        return self.chosen_kind() == "Named component"

    def source_name(self) -> str:
        """Named Components' planner: the exact name; refuse text PythonQt cannot round-trip."""
        text = str(get(self.source_edit.text))
        if any(c in text for c in ("\x00", " ", " ", " ")):
            raise ValueError(
                "Enter a glyph name without control or non-breaking characters."
            )
        if not text.strip():
            raise ValueError("Enter a component source name.")
        return text.strip()

    def planner(self) -> Any:
        package = self.package
        if self.chosen_kind() == "Serif components":
            return lambda glyph, master, layer: changes(package, glyph, master, layer)
        return lambda glyph, master, layer: decompose_changes(
            package, glyph, layer, master
        )

    def make_plan(self, package: Any, glyphs: list[Any], facts: Any) -> tuple[Any, str]:
        """Named: preview without letting a kept row block other eligible items."""
        if not self.named():
            return super().make_plan(package, glyphs, facts)
        try:
            return make_plan(
                package, glyphs, self.chosen_masters(), self.source_name(), facts
            ), ""
        except (ValueError, RuntimeError, TimeoutError) as error:
            return component_writer.Plan(), str(error)

    def final_plan(self, package: Any, glyphs: list[Any], facts: Any, plan: Any) -> Any:
        """Named: copy the subtrees on Apply, before history opens."""
        if not self.named():
            return plan
        return make_plan(
            package, glyphs, self.chosen_masters(), self.source_name(), facts, copy=True
        )

    def editor(self) -> Any:
        if self.named():
            return NamedEditor(unlock=True)
        return component_writer.EjectEditor(unlock=True)

    def done_text(self, result: dict, plan: Any) -> str:
        if not self.named():
            return super().done_text(result, plan)
        message = f"Decomposed {result['edits']} occurrences on {result['layers']} layers; review kept rows above."
        return edit_guards.append_note(message, result)


__all__ = [
    "SCOPES", "SCOPE_SETTINGS", "DecomposePanel", "NamedEditor", "changes", "checked_parts",
    "decompose_changes", "flatten_parts", "make_plan", "source_contours",
]  # fmt: skip
