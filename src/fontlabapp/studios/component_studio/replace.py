# this_file: src/fontlabapp/studios/component_studio/replace.py
# SPDX-License-Identifier: Apache-2.0
"""Replace tab (Replace Reference): replace the base glyph of matching components, keep their placement.

The original's rules are kept unchanged (``users_of``, ``matrix_of``,
``replace_changes``, ``replace_problem``, ``ReplaceEditor``): every
component that refers to glyph X now refers to glyph Y; offset, scale,
slant, name, note and lock stay, because the base name of the existing
component is set in place and FontLab rebuilds it (nothing is deleted and
re-created). A component is a red row, and the batch is refused, when the
new glyph has no layer for that master, when the new glyph uses the edited
glyph (it would show itself), or when the component shares its element data.
"Glyphs": Selected glyphs (default) or Whole font; "Masters": current
master (default) or all. Both name fields complete glyph names; the dry
run waits 250 ms after the last key press. Apply writes the listed changes
as one ``Component Studio: replace component reference <subject>`` Undo
step, then reads every component back (base name and unchanged matrix).
Auto layers are listed and kept; a glyph that owns auto layers or is a base
of one is refused (no opt-in, as in the original).
"""

from typing import Any

from PythonQt import QtCore, QtGui

import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - the package __getattr__ is native
import fontlabapp.core.scripting as scripting  # noqa: PLR0402 - the package __getattr__ is native

from .._kerning_ui import combo, get, line_edit, row
from . import _shared

#: The original's module name, read by the verbatim functions below.
component_writer = _shared.Modules("components")

DEBOUNCE_MS = 250  # replan this long after the last key press


# ---------------------------------------------------------------- verbatim original
# Replace Reference
def users_of(facts: history.AutoFacts, name: str) -> set[str]:
    """Every glyph that shows `name`, directly or through other components.

    When the new base is among the users of the edited glyph, the edited glyph
    would contain itself.
    """
    seen, todo = {name}, [name]
    while todo:
        for user in facts.users.get(todo.pop(), ()):
            if user not in seen:
                seen.add(user)
                todo.append(user)
    return seen - {name}


def matrix_of(shape: Any) -> tuple[float, ...]:
    """The six transform numbers, to prove that the placement did not move."""
    m = shape.transform
    return (m.m11(), m.m12(), m.m21(), m.m22(), m.dx(), m.dy())


def replace_changes(
    package: Any,
    glyph: Any,
    layer: Any,
    master: str,
    names: tuple[str, str],
    facts: history.AutoFacts,
) -> list[component_writer.Change]:
    """One row per component of `old` on the layer, with its block reason if any."""
    old, new = names
    rows: list[component_writer.Change] = []
    for shape in component_writer.components(layer):
        if component_writer.base_of(shape) != old:
            continue
        where = component_writer.offset_text(component_writer.offset(shape))
        problem = replace_problem(package, glyph, shape, master, new, facts)
        if problem:
            rows.append(component_writer.Change(old, where, "", problem=problem))
        else:
            rows.append(component_writer.Change(old, where, new, (shape.id, new)))
    return rows


def replace_problem(
    package: Any,
    glyph: Any,
    shape: Any,
    master: str,
    new: str,
    facts: history.AutoFacts,
) -> str:
    """Why `shape` cannot show `new`, or "".

    The new base needs the layer the component reads: its own layer name, if
    it names one, else the master.
    """
    wanted = shape.shapeData.componentLayer or master
    target = package.findName(new)
    if target is None or component_writer.layer_of(target, wanted) is None:
        return f"{new} has no layer {wanted}"
    if new == glyph.name or new in users_of(facts, glyph.name):
        return f"{new} uses {glyph.name}: the component would show itself"
    if int(shape.shapeData.referenceCount) > 1:
        return "shared element data: change it in FontLab"
    return ""


class ReplaceEditor(component_writer.Editor):
    """Set the base glyph name of each planned component in place."""

    def prepare(self, layer: Any, edits: list[Any]) -> list[Any]:
        steps = []
        for shape_id, new in edits:
            shape = layer.shapes[component_writer.shape_index(layer, shape_id)]
            steps.append((shape, new, matrix_of(shape)))
        return steps

    def write(self, layer: Any, steps: list[Any]) -> None:
        for shape, new, _ in steps:
            shape.shapeData.componentGlyph = new
            component_writer.refreshed(shape)

    def check(self, prepared: list[tuple[Any, list[Any]]]) -> list[str]:
        missed: list[str] = []
        for layer, steps in prepared:
            for shape, new, matrix in steps:
                now = matrix_of(shape)
                moved = any(
                    abs(a - b) >= component_writer.EPSILON
                    for a, b in zip(now, matrix, strict=True)
                )
                if component_writer.base_of(shape) != new or moved:
                    missed.append(f"{layer.name}/{new}")
        return missed


# ---------------------------------------------------------------- tab
class ReplacePanel(_shared.ComponentPanel):
    """Old and new glyph names, glyph scope and master scope."""

    ACTION, DONE, UNDO = "Replace", "Replaced", "replace component reference"
    HEADERS: tuple[str, ...] = ("Glyph · master", "Component", "Offset", "Becomes")

    def build_controls(self, form: Any) -> None:
        self.old_edit = line_edit(
            self.widget,
            "",
            "component to replace, e.g. period",
            self.contain(self.typed),
        )
        row(self.widget, form, "Replace", self.old_edit)
        self.new_edit = line_edit(
            self.widget,
            "",
            "new component glyph, e.g. period.alt",
            self.contain(self.typed),
        )
        row(self.widget, form, "With", self.new_edit)
        self.glyph_scope = combo(
            self.widget, ["Selected glyphs", "Whole font"], self.contain(self.refresh)
        )
        row(self.widget, form, "Glyphs", self.glyph_scope)
        self.scope_box(form)
        self.timer = QtCore.QTimer(self.widget)
        self.timer.setSingleShot(True)
        self.timer.setInterval(DEBOUNCE_MS)
        self.timer.timeout.connect(self.contain(self.replan))

    def glyph_names(self) -> list[str]:
        if get(self.glyph_scope.currentIndex) == 1:
            return [name for name, _ in scripting.names_font_glyphs()]
        return self.tool.selected_names()

    def on_reload(self) -> None:
        """Offer every glyph name of the font for completion."""
        if self.package is None:
            return
        names = [name for name, _ in scripting.names_font_glyphs()]
        for edit in (self.old_edit, self.new_edit):
            completer = QtGui.QCompleter(names, self.widget)
            completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
            completer.setFilterMode(QtCore.Qt.MatchContains)
            edit.setCompleter(completer)

    def typed(self) -> None:
        """Wait for a pause in typing before the preview scans again."""
        self.apply_button.setEnabled(False)
        self.timer.start()

    def names(self) -> tuple[str, str]:
        """(old, new), checked. ValueError tells what to type."""
        old, new = (
            str(get(self.old_edit.text)).strip(),
            str(get(self.new_edit.text)).strip(),
        )
        if not old or not new:
            raise ValueError("Type both glyph names.")
        if old == new:
            raise ValueError("The two names are the same.")
        if self.package is None or self.package.findName(new) is None:
            raise ValueError(f"No glyph named {new}.")
        return old, new

    def summary(self, plan: Any) -> str:
        if not plan.rows:
            try:
                self.names()
            except ValueError as error:
                return str(error)
            return "No component of that glyph in scope"
        return super().summary(plan)

    def planner(self) -> Any:
        package, names, facts = self.package, self.names(), self.facts
        return lambda glyph, master, layer: replace_changes(
            package, glyph, layer, master, names, facts
        )

    def make_plan(self, package: Any, glyphs: list[Any], facts: Any) -> tuple[Any, str]:
        """The original plans with fresh component data: Apply rescans ``facts`` first."""
        self.facts = facts
        return super().make_plan(package, glyphs, facts)

    def editor(self) -> Any:
        return ReplaceEditor()


__all__ = [
    "DEBOUNCE_MS", "ReplaceEditor", "ReplacePanel", "matrix_of", "replace_changes",
    "replace_problem", "users_of",
]  # fmt: skip
