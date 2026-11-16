# this_file: src/fontlabapp/studios/transform_studio/tabs.py
# SPDX-License-Identifier: Apache-2.0
"""The three Transform Studio tabs (Transform, Slant, Rotate & reflect) and the shared ``Tab`` base.

What: each tab is a plain Qt widget over the shared ``Studio`` state with the
same glyph row (names field, "Use font selection", preview master, "All
masters", the bases opt-in where the original script offered it) and a
sortable ``GlyphTable`` of the last plan: one row per change, or one row per
skipped layer with its note. Choosing a row shows that glyph in the TGlyph
preview. Every action has a "Preview" button that plans, fills the table and
draws the planned outline as a ghost (``preview.set_overlay``) without writing,
and an apply button that writes one labelled Undo step. Hinted layers are
skipped unless "Edit hinted layers anyway" is ticked or their hints are removed.
Why: one window replaces six Scriptmix ``Scripts/Contours`` tools (Phase D A6).
``Tab`` and the field helpers are reused by ``fontlabapp.studios.align_nudge.tabs``.
"""

from collections.abc import Callable, Sequence
from typing import Any

from PythonQt import QtGui

import fontlabapp.fontui as fontui

from . import model
from .session import NO_FONT, Planner, Row, Studio

PLAN_COLUMNS = ("Glyph", "Master", "Item", "Before", "After", "Note")
ALLOW_BASES_LABEL = "Edit bases of auto glyphs anyway"  # Scriptmix "Also edit bases of automatic composites", off
ALLOW_HINTED_LABEL = "Edit hinted layers anyway"


def _button(owner: Any, layout: Any, text: str, slot: Callable[[], Any]) -> Any:
    button = QtGui.QPushButton(text, owner)
    button.setAccessibleName(text)
    button.clicked.connect(lambda *args: slot())
    layout.addWidget(button)
    return button


def _field(
    owner: Any, layout: Any, label: str, placeholder: str = "", text: str = ""
) -> Any:
    layout.addWidget(QtGui.QLabel(label, owner))
    field = QtGui.QLineEdit(owner)
    field.setPlaceholderText(placeholder)
    field.setAccessibleName(label)
    field.setText(text)
    layout.addWidget(field)
    return field


def _combo(
    owner: Any, layout: Any, label: str, items: Sequence[str], index: int = 0
) -> Any:
    layout.addWidget(QtGui.QLabel(label, owner))
    box = QtGui.QComboBox(owner)
    box.setAccessibleName(label)
    box.addItems(list(items))
    box.setCurrentIndex(index)
    layout.addWidget(box)
    return box


def _dspin(owner: Any, layout: Any, label: str, bounds: tuple[float, float], value: float,
           decimals: int = 2, suffix: str = "") -> Any:  # fmt: skip
    layout.addWidget(QtGui.QLabel(label, owner))
    spin = QtGui.QDoubleSpinBox(owner)
    spin.setAccessibleName(label)
    spin.setDecimals(decimals)
    spin.setRange(*bounds)
    spin.setValue(value)
    if suffix:
        spin.setSuffix(suffix)
    layout.addWidget(spin)
    return spin


def _check(owner: Any, layout: Any, label: str, on: bool) -> Any:
    box = QtGui.QCheckBox(label, owner)
    box.setAccessibleName(label)
    box.setChecked(on)
    layout.addWidget(box)
    return box


def _get(value: Any) -> Any:
    return value() if callable(value) else value


def _text(field: Any) -> str:
    return str(_get(field.text)).strip()


def _names(text: str) -> list[str]:
    return [name for name in text.replace("/", " ").replace(",", " ").split() if name]


def _number(spin: Any) -> float:
    return float(_get(spin.value))


def _index(box: Any) -> int:
    return int(_get(box.currentIndex))


def _on(box: Any) -> bool:
    return bool(_get(box.isChecked))


def records(rows: Sequence[Row]) -> list[tuple[str, str, tuple[str, ...]]]:
    """Table rows: one per change, or one per layer without changes."""
    out = []
    for row in rows:
        if not row.changes:
            out.append(
                (
                    row.glyph,
                    row.master,
                    (row.master, "", "", "", row.note or "no change"),
                )
            )
        for change in row.changes:
            note = change.problem or row.note
            out.append(
                (
                    row.glyph,
                    row.master,
                    (row.master, change.name, change.old, change.new, note),
                )
            )
    return out


class Tab:
    """A tab bound to the studio: glyph row, master row, the action area and a result table."""

    COLUMNS: Sequence[str] = PLAN_COLUMNS
    BASES = True  # False where the original script never offered the bases opt-in

    def __init__(self, studio: Studio) -> None:
        self.studio = studio
        self.app = studio.APP
        self.widget = QtGui.QWidget()
        self.layout = QtGui.QVBoxLayout(self.widget)
        self.records: list[tuple[str, str | None, tuple[Any, ...]]] = []
        glyphs = QtGui.QHBoxLayout()
        self.glyphs_field = _field(self.widget, glyphs, "Glyphs", "A B /Aacute")
        _button(self.widget, glyphs, "Use font selection", self.use_selection)
        self.layout.addLayout(glyphs)
        masters = QtGui.QHBoxLayout()
        masters.addWidget(QtGui.QLabel("Preview master", self.widget))
        self.master_box = QtGui.QComboBox(self.widget)
        self.master_box.setAccessibleName("Preview master")
        self.master_box.currentIndexChanged.connect(
            lambda *args: self._master_changed()
        )
        masters.addWidget(self.master_box)
        self.all_masters = _check(self.widget, masters, "All masters", False)
        self.allow_bases = _check(self.widget, masters, ALLOW_BASES_LABEL, False)
        self.allow_bases.setVisible(self.BASES)
        self.write_note = QtGui.QLabel("", self.widget)
        masters.addWidget(self.write_note, 1)
        self.layout.addLayout(masters)
        self.controls()
        hints = QtGui.QHBoxLayout()
        hints.addWidget(QtGui.QLabel("Hinted layers are skipped.", self.widget), 1)
        self.allow_hinted = _check(self.widget, hints, ALLOW_HINTED_LABEL, False)
        _button(self.widget, hints, "Remove PostScript hints", self.remove_hints)
        self.layout.addLayout(hints)
        self.table = fontui.glyph_table(list(self.COLUMNS), self.widget)
        self.table.row_selected.connect(self.row_chosen)
        self.layout.addWidget(studio.shell.embed(self.table), 1)
        studio.views.append(self.refresh)

    def controls(self) -> None:  # pragma: no cover - overridden
        pass

    def line(self) -> Any:
        layout = QtGui.QHBoxLayout()
        self.layout.addLayout(layout)
        return layout

    # Shared state ----------------------------------------------------------
    def names(self) -> list[str]:
        return _names(_text(self.glyphs_field))

    def every_master(self) -> bool:
        return _on(self.all_masters)

    def bases_allowed(self) -> bool:
        return bool(self.BASES and _on(self.allow_bases))

    def hinted_allowed(self) -> bool:
        return _on(self.allow_hinted)

    def use_selection(self) -> list[str]:
        names = self.studio.use_selection()
        self.glyphs_field.setText(" ".join(names))
        if names:
            self.studio.show_glyph(names[0])
        else:
            self.studio.say(f"{self.app}: Select glyphs in the Font window first.")
        return names

    def refresh(self) -> None:
        studio = self.studio
        self.master_box.blockSignals(True)
        self.master_box.clear()
        self.master_box.addItems(list(studio.masters))
        if studio.master in studio.masters:
            self.master_box.setCurrentIndex(studio.masters.index(studio.master))
        self.master_box.blockSignals(False)
        if not studio.master:
            self.write_note.setText(NO_FONT)
        else:
            self.write_note.setText(
                f"Writes go to {studio.master} unless All masters is on."
            )
        self.table.set_rows(self.records)

    def _master_changed(self) -> None:
        name = _get(self.master_box.currentText)
        if name and name != self.studio.master:
            self.studio.set_glyphs(self.names())
            self.studio.choose_master(name)
            self.studio._refresh()

    def row_chosen(self, name: str, layer: Any = None) -> None:
        if not name:
            return
        if layer and layer != self.studio.master and layer in self.studio.masters:
            self.studio.master = layer
            self.studio._refresh()
        self.studio.show_glyph(name)

    def show_rows(self, rows: Sequence[Row]) -> None:
        self.records = records(rows)
        self.table.set_rows(self.records)

    def preview(self, planner: Planner) -> list[Row]:
        """Plan ``planner`` without writing; fill the table and draw the ghost of the previewed glyph."""
        names = self.names()
        self.studio.set_glyphs(names)
        rows = self.studio.plan(
            planner,
            names,
            all_masters=self.every_master(),
            allow_hinted=self.hinted_allowed(),
        )
        self.show_rows(rows)
        changes = sum(1 for row in rows for change in row.changes if change.edit)
        self.studio.say(
            f"{self.app}: {changes} change(s) planned on {len(rows)} layer(s); nothing written."
        )
        if names:
            self.studio.show_glyph(names[0])
        self.studio.ghost(rows)
        return rows

    def run(self, action: str, planner: Planner) -> bool:
        """Write ``planner`` to the chosen glyphs as one labelled step; show the plan."""
        chosen = self.names()
        self.studio.set_glyphs(chosen)
        done = self.studio.apply(action, planner, chosen, all_masters=self.every_master(),
                                 allow_bases=self.bases_allowed(), allow_hinted=self.hinted_allowed())  # fmt: skip
        self.show_rows(self.studio.rows)
        if chosen:
            self.studio.show_glyph(chosen[0])
        return done

    def guard(self, action: Callable[[], Any]) -> Any:
        """Run ``action``; a ValueError from a field becomes the status line."""
        try:
            return action()
        except ValueError as error:
            self.studio.say(f"{self.app}: {error}")
            return False

    def remove_hints(self) -> int:
        """The hint opt-in: remove PostScript hints from the chosen layers, one Undo step per layer."""
        names = self.names()
        self.studio.set_glyphs(names)
        removed = self.studio.remove_hints(names, all_masters=self.every_master())
        if removed:
            self.studio.say(
                f"{self.app}: removed PostScript hints from {removed} layer(s)."
            )
        return removed

    def pair(
        self, layout: Any, subject: str, planner: Callable[[], Planner], action: str
    ) -> None:
        """A "Preview …" and an apply button for one planner."""
        _button(
            self.widget,
            layout,
            f"Preview {subject}",
            lambda: self.guard(lambda: self.preview(planner())),
        )
        _button(
            self.widget,
            layout,
            action[0].upper() + action[1:],
            lambda: self.guard(lambda: self.run(action, planner())),
        )


class TransformTab(Tab):
    """Scriptmix Transform: scale, skew, rotate and move about a chosen origin."""

    def controls(self) -> None:
        line = self.line()
        self.scale_x = _dspin(
            self.widget, line, "Scale x %", model.SCALE_RANGE, 100.0, 1
        )
        self.scale_y = _dspin(
            self.widget, line, "Scale y %", model.SCALE_RANGE, 100.0, 1
        )
        self.skew = _dspin(self.widget, line, "Skew °", model.SKEW_RANGE, 0.0)
        self.rotate = _dspin(self.widget, line, "Rotate °", model.ROTATE_RANGE, 0.0)
        line = self.line()
        self.move_x = _dspin(self.widget, line, "Move x", model.MOVE_RANGE, 0.0)
        self.move_y = _dspin(self.widget, line, "Move y", model.MOVE_RANGE, 0.0)
        self.origin = _combo(self.widget, line, "Origin", model.ORIGINS, 0)
        self.anchors = _check(self.widget, line, "Move anchors too", True)
        self.pair(self.line(), "transform", self.planner, "transform")

    def planner(self) -> Planner:
        lin = model.linear(
            _number(self.scale_x),
            _number(self.scale_y),
            _number(self.skew),
            _number(self.rotate),
        )
        choice, move, anchors = (
            _index(self.origin),
            (_number(self.move_x), _number(self.move_y)),
            _on(self.anchors),
        )
        return lambda name, master, snap: model.transform_planner_changes(
            snap, lin, choice, move, anchors
        )


class SlantTab(Tab):
    """Scriptmix Slant (shear about a pivot) and Smart Slant (shear that keeps spacing)."""

    def controls(self) -> None:
        line = self.line()
        self.angle = _dspin(
            self.widget, line, "Slant angle °", model.SLANT_RANGE, model.SLANT_DEFAULT
        )
        self.italic = _button(
            self.widget, line, "Current master’s italic angle", self.use_italic
        )
        self.pivot = _combo(self.widget, line, "Pivot", model.PIVOTS, 1)
        self.anchors = _check(self.widget, line, "Slant anchors too", True)
        self.pair(self.line(), "slant", self.planner, "slant")
        line = self.line()
        self.smart_angle = _dspin(
            self.widget,
            line,
            "Smart slant angle °",
            model.SMART_RANGE,
            model.SLANT_DEFAULT,
        )
        self.sidebearings = _check(
            self.widget, line, "Keep sidebearings (adjust advance)", True
        )
        self.smart_anchors = _check(
            self.widget, line, "Slant anchors too (smart)", True
        )
        self.pair(self.line(), "smart slant", self.smart_planner, "smart slant")

    def refresh(self) -> None:
        super().refresh()
        try:
            angle = self.studio.italic_angle()
        except ValueError:
            angle = 0.0
        self.italic.setText(f"Current master’s italic angle ({angle:g}°)")
        self.italic.setEnabled(bool(angle))

    def use_italic(self) -> float:
        """Set the slant to the current master's italic angle (FontLab stores it negated)."""
        angle = -self.guard(self.studio.italic_angle)
        self.angle.setValue(angle)
        return angle

    def planner(self) -> Planner:
        angle, half, anchors = (
            _number(self.angle),
            _index(self.pivot) == 1,
            _on(self.anchors),
        )
        model.slant_matrix(angle, 0.0)

        def plan(name: str, master: str, snap: Any) -> Any:
            return model.slant_changes(
                snap,
                angle,
                self.studio.x_height(master) / 2.0 if half else 0.0,
                anchors,
            )

        return plan

    def smart_planner(self) -> Planner:
        angle, sidebearings, anchors = (
            _number(self.smart_angle),
            _on(self.sidebearings),
            _on(self.smart_anchors),
        )
        model.smart_check(angle)
        return lambda name, master, snap: model.smart_changes(
            snap, angle, sidebearings, anchors
        )


class RotateTab(Tab):
    """Scriptmix Rotate Selection and Reflect Selection Horizontally/Vertically."""

    BASES = False  # the originals always refused bases of automatic composites

    def controls(self) -> None:
        line = self.line()
        self.angle = _dspin(
            self.widget,
            line,
            "Angle (+ CCW, − CW)",
            model.ROTATE_RANGE,
            model.ROTATE_DEFAULT,
        )
        self.pair(line, "rotation", self.planner, "rotate")
        line = self.line()
        for degrees in model.PRESETS:
            for sign, word in ((1, "CCW"), (-1, "CW")):
                _button(
                    self.widget,
                    line,
                    f"{degrees}° {word}",
                    lambda value=sign * degrees: self.preset(value),
                )
        line = self.line()
        for axis in model.REFLECTIONS:
            self.pair(
                line,
                f"{axis} reflection",
                lambda axis=axis: self.reflect_planner(axis),
                f"reflect {axis}",
            )

    def preset(self, value: float) -> Any:
        """A preset button sets the angle and applies immediately, as in the original."""
        self.angle.setValue(value)
        return self.guard(lambda: self.run("rotate", self.planner()))

    def planner(self) -> Planner:
        lin = model.rotation_linear(_number(self.angle))
        return lambda name, master, snap: model.selection_changes(snap, lin)

    def reflect_planner(self, axis: str) -> Planner:
        lin = model.REFLECTIONS[axis]
        return lambda name, master, snap: model.selection_changes(snap, lin)


TAB_CLASSES = (
    ("Transform", TransformTab),
    ("Slant", SlantTab),
    ("Rotate & reflect", RotateTab),
)

__all__ = ["TAB_CLASSES", "RotateTab", "SlantTab", "Tab", "TransformTab", "records"]
