# this_file: src/fontlabapp/studios/component_studio/offsets.py
# SPDX-License-Identifier: Apache-2.0
"""Offsets tab (Copy Offsets Between Masters): copy component offsets from one master to others.

The original's rules are kept unchanged (``offset_changes``): components
are matched by position and base glyph name; a target layer with other
components, or in another order, is listed as "different components,
kept". With "Scale x by advance-width ratio" (off by default) the
horizontal offset is multiplied by target width / source width and rounded
half up; the vertical offset is copied as it is. Only the offset changes.
"From" defaults to the current master; "To" lists every other master, all
ticked; "Tick at least one target master." refuses an empty choice.
Apply writes the listed offsets as one
``Component Studio: copy component offsets <subject>`` Undo step
(``MoveEditor``). Auto layers are listed and kept; a glyph that owns auto
layers or is a base of one is refused (no opt-in, as in the original).
"""

from typing import Any

from PythonQt import QtCore, QtGui

from .._kerning_ui import check, combo, get, row
from . import _shared

#: The original's module names, read by the verbatim function below.
component_writer = _shared.Modules("components")
component_panel = _shared.Modules("panel")


# ---------------------------------------------------------------- verbatim original
# Copy Offsets Between Masters
def offset_changes(
    source: Any, target: Any, scale: bool
) -> list[component_writer.Change]:
    """One row per component of the target: current and new offset.

    Different component lists give one note row and no edit.
    """
    src, dst = component_writer.components(source), component_writer.components(target)
    if not src:
        return []
    if [component_writer.base_of(s) for s in src] != [
        component_writer.base_of(s) for s in dst
    ]:
        names = " + ".join(component_writer.base_of(s) for s in dst) or "none"
        return [component_writer.Change(names, "", "different components, kept")]
    ratio = 1.0
    if scale and source.advanceWidth:
        ratio = float(target.advanceWidth) / float(source.advanceWidth)
    rows: list[component_writer.Change] = []
    for old_shape, shape in zip(src, dst, strict=True):
        dx, dy = component_writer.offset(old_shape)
        new = (float(component_writer.half_up(dx * ratio)) if scale else dx, dy)
        old = component_writer.offset(shape)
        if all(
            abs(new[axis] - old[axis]) < component_writer.EPSILON for axis in (0, 1)
        ):
            rows.append(
                component_writer.Change(
                    component_writer.base_of(shape),
                    component_writer.offset_text(old),
                    "same",
                )
            )
        else:
            rows.append(
                component_writer.Change(
                    component_writer.base_of(shape),
                    component_writer.offset_text(old),
                    component_writer.offset_text(new),
                    (shape.id, new),
                )
            )
    return rows


# ---------------------------------------------------------------- tab
class OffsetsPanel(_shared.ComponentPanel):
    """Source master, target checklist, scale option; one row per component."""

    ACTION, DONE, UNDO = "Copy", "Moved", "copy component offsets"
    HEADERS: tuple[str, ...] = ("Glyph · master", "Component", "Offset", "New")

    def build_controls(self, form: Any) -> None:
        self.ticked: set[str] = set()
        self.source_box = combo(self.widget, [], self.contain(self.retarget))
        row(self.widget, form, "From", self.source_box)
        self.target_list = QtGui.QListWidget(self.widget)
        self.target_list.setAlternatingRowColors(True)
        self.target_list.setMinimumHeight(90)
        row(self.widget, form, "To", self.target_list)
        self.scale_box = check(self.widget, form, "Scale x by advance-width ratio", False,
                               self.contain(self.replan))  # fmt: skip
        self.target_list.itemChanged.connect(self.contain(self.toggled))

    def on_reload(self) -> None:
        """Refill the source combo; keep the chosen source when it still exists."""
        masters = list(self.tool.masters)
        keep = self.source()
        self.source_box.blockSignals(True)
        self.source_box.clear()
        for master in masters:
            self.source_box.addItem(master)
        start = keep if keep in masters else self.current_master
        if start in masters:
            self.source_box.setCurrentIndex(masters.index(start))
        self.source_box.blockSignals(False)
        if not self.ticked:
            self.ticked = set(masters)
        self.fill_targets()

    def source(self) -> str:
        """Chosen source master name, or '' without a font."""
        if get(self.source_box.currentIndex) < 0:
            return ""
        return str(get(self.source_box.currentText))

    def fill_targets(self) -> None:
        """Every master except the source, ticked as before."""
        self.target_list.blockSignals(True)
        self.target_list.clear()
        for master in self.tool.masters:
            if master == self.source():
                continue
            item = QtGui.QListWidgetItem(master)
            item.setForeground(component_panel.ink())
            item.setData(QtCore.Qt.UserRole, master)
            item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(
                QtCore.Qt.Checked if master in self.ticked else QtCore.Qt.Unchecked
            )
            self.target_list.addItem(item)
        self.target_list.blockSignals(False)

    def retarget(self) -> None:
        self.fill_targets()
        self.replan()

    def toggled(self, item: Any) -> None:
        master = item.data(QtCore.Qt.UserRole)
        if item.checkState() == QtCore.Qt.Checked:
            self.ticked.add(master)
        else:
            self.ticked.discard(master)
        self.replan()

    def chosen_masters(self) -> list[str]:
        source = self.source()
        return [m for m in self.tool.masters if m != source and m in self.ticked]

    def planner(self) -> Any:
        source, scale = self.source(), bool(get(self.scale_box.isChecked))
        if not self.chosen_masters():
            raise ValueError("Tick at least one target master.")

        def plan(glyph: Any, master: str, layer: Any) -> list[Any]:
            origin = component_writer.layer_of(glyph, source)
            return offset_changes(origin, layer, scale) if origin is not None else []

        return plan

    def editor(self) -> Any:
        return component_writer.MoveEditor()


__all__ = ["OffsetsPanel", "offset_changes"]
