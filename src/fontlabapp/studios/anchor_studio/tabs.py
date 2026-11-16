# this_file: src/fontlabapp/studios/anchor_studio/tabs.py
# SPDX-License-Identifier: Apache-2.0
"""The five Anchor Studio tabs: Place, Align, Rename & delete, Clean-up and Overlays.

What: each tab is a plain Qt widget over the shared ``Studio`` state with the
same glyph row (names field, "Use font selection", preview master and "All
masters") and a sortable ``GlyphTable`` of the last plan or reading: one row
per anchor change, or one row per skipped layer with its note. Choosing a row
shows that glyph in the TGlyph preview (contract §1.8). Every writing action
has a "Preview" button that plans without writing and an apply button that
writes one labelled Undo step. The Overlays tab only reads.
Why: one window replaces the eleven Scriptmix ``Scripts/Anchors`` tools (Phase D A3).
Used by ``fontlabapp.studios.anchor_studio`` (tab builders and ``show``).
"""

from collections.abc import Callable, Sequence
from typing import Any

from PythonQt import QtCore, QtGui

import fontlabapp.fontui as fontui

from . import APP, model
from .session import NO_FONT, Row, Studio

ANCHOR_COLUMNS = ("Glyph", "Master", "Anchor", "x", "y")
PLAN_COLUMNS = ("Glyph", "Master", "Anchor", "Before", "After", "Note")
ALLOW_BASES_LABEL = "Edit bases of auto glyphs anyway"  # same opt-in as Spacing Studio, off by default
SCOPES = ("Glyph list", "Whole font")
OFFSET_RANGE = (-1000, 1000)
ANGLE_RANGE = (-45, 45)
STEP_RANGE = (1, 500)
STEP_DEFAULT = 10
FRACTION_DEFAULT = 50
SNAP_METRIC_DEFAULT = 1  # x-height
CLOUD_DEFAULT = "top"
CENTRE_DEFAULT = "top, bottom"


def _button(owner: Any, layout: Any, text: str, slot: Callable[[], Any]) -> Any:
    button = QtGui.QPushButton(text, owner)
    button.setAccessibleName(text)
    button.clicked.connect(lambda *args: slot())
    layout.addWidget(button)
    return button


def _field(owner: Any, layout: Any, label: str, placeholder: str = "", text: str = "") -> Any:
    layout.addWidget(QtGui.QLabel(label, owner))
    field = QtGui.QLineEdit(owner)
    field.setPlaceholderText(placeholder)
    field.setAccessibleName(label)
    field.setText(text)
    layout.addWidget(field)
    return field


def _combo(owner: Any, layout: Any, label: str, items: Sequence[str], index: int = 0) -> Any:
    layout.addWidget(QtGui.QLabel(label, owner))
    box = QtGui.QComboBox(owner)
    box.setAccessibleName(label)
    box.addItems(list(items))
    box.setCurrentIndex(index)
    layout.addWidget(box)
    return box


def _spin(owner: Any, layout: Any, label: str, bounds: tuple[int, int], value: int) -> Any:
    layout.addWidget(QtGui.QLabel(label, owner))
    spin = QtGui.QSpinBox(owner)
    spin.setAccessibleName(label)
    spin.setRange(*bounds)
    spin.setValue(value)
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


def _value(spin: Any) -> int:
    return int(_get(spin.value))


def _on(box: Any) -> bool:
    return bool(_get(box.isChecked))


def records(rows: Sequence[Row]) -> list[tuple[str, str, tuple[str, ...]]]:
    """Table rows: one per anchor change, or one per layer without changes."""
    out = []
    for row in rows:
        if not row.changes:
            out.append((row.glyph, row.master, (row.master, "", "", "", row.note or "no change")))
        for change in row.changes:
            note = change.problem or row.note
            out.append((row.glyph, row.master, (row.master, change.name, change.old, change.new, note)))
    return out


class Tab:
    """A tab bound to the studio: glyph row, master row, the action area and a result table."""

    COLUMNS: Sequence[str] = PLAN_COLUMNS
    WRITES = True  # writing tabs show the bases opt-in and the hint remover

    def __init__(self, studio: Studio) -> None:
        self.studio = studio
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
        self.master_box.currentIndexChanged.connect(lambda *args: self._master_changed())
        masters.addWidget(self.master_box)
        self.all_masters = _check(self.widget, masters, "All masters", False)
        self.all_masters.setVisible(self.WRITES)
        self.allow_bases = _check(self.widget, masters, ALLOW_BASES_LABEL, False)
        self.allow_bases.setVisible(self.WRITES)
        self.write_note = QtGui.QLabel("", self.widget)
        masters.addWidget(self.write_note, 1)
        self.layout.addLayout(masters)
        self.controls()
        if self.WRITES:
            hints = QtGui.QHBoxLayout()
            hints.addWidget(QtGui.QLabel("Hinted layers are skipped.", self.widget), 1)
            _button(self.widget, hints, "Remove PostScript hints", self.remove_hints)
            self.layout.addLayout(hints)
        self.table = fontui.glyph_table(list(self.COLUMNS), self.widget)
        self.table.row_selected.connect(self.row_chosen)
        self.layout.addWidget(studio.shell.embed(self.table), 1)
        studio.views.append(self.refresh)

    def controls(self) -> None:  # pragma: no cover - overridden
        pass

    # Shared state ----------------------------------------------------------
    def names(self) -> list[str]:
        return _names(_text(self.glyphs_field))

    def every_master(self) -> bool:
        return bool(self.WRITES and _on(self.all_masters))

    def bases_allowed(self) -> bool:
        return bool(self.WRITES and _on(self.allow_bases))

    def use_selection(self) -> list[str]:
        names = self.studio.use_selection()
        self.glyphs_field.setText(" ".join(names))
        if names:
            self.studio.show_glyph(names[0])
        else:
            self.studio.say(f"{APP}: Select glyphs in the Font window first.")
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
        elif self.WRITES:
            self.write_note.setText(f"Writes go to {studio.master} unless All masters is on.")
        else:
            self.write_note.setText(f"Reads {studio.master}; nothing is written.")
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

    def chosen(self) -> list[str]:
        """The glyphs an action reads or writes (tabs with a scope widen it)."""
        return self.names()

    def preview(self, planner: model.Planner, *, masters: Sequence[str] | None = None) -> list[Row]:
        """Plan ``planner`` without writing; the table shows every change and skip."""
        names = self.chosen()
        self.studio.set_glyphs(names)
        rows = self.studio.plan(planner, names, all_masters=self.every_master(), masters=masters)
        self.show_rows(rows)
        changes = sum(len(row.edits) for row in rows)
        self.studio.say(f"{APP}: {changes} change(s) planned on {len(rows)} layer(s); nothing written.")
        if names:
            self.studio.show_glyph(names[0])
        return rows

    def run(self, action: str, planner: model.Planner, *, masters: Sequence[str] | None = None) -> bool:
        """Write ``planner`` to the chosen glyphs as one labelled step; show the plan."""
        chosen = self.chosen()
        self.studio.set_glyphs(chosen)
        done = self.studio.apply(action, planner, chosen, all_masters=self.every_master(), masters=masters,
                                 allow_bases=self.bases_allowed())  # fmt: skip
        self.show_rows(self.studio.rows)
        if chosen:
            self.studio.show_glyph(chosen[0])
        return done

    def guard(self, action: Callable[[], Any]) -> Any:
        """Run ``action``; a ValueError from a field becomes the status line."""
        try:
            return action()
        except ValueError as error:
            self.studio.say(f"{APP}: {error}")
            return False

    def remove_hints(self) -> int:
        """The hint opt-in: remove PostScript hints from the chosen layers, one Undo step per layer."""
        names = self.names()
        self.studio.set_glyphs(names)
        removed = self.studio.remove_hints(names, all_masters=self.every_master())
        if removed:
            self.studio.say(f"{APP}: removed PostScript hints from {removed} layer(s).")
        return removed

    def pair(self, layout: Any, subject: str, planner: Callable[[], model.Planner], action: str,
             *, masters: Callable[[], Sequence[str] | None] = lambda: None) -> None:  # fmt: skip
        """A "Preview …" and an apply button for one planner."""
        _button(self.widget, layout, f"Preview {subject}",
                lambda: self.guard(lambda: self.preview(planner(), masters=masters())))  # fmt: skip
        _button(self.widget, layout, action.capitalize(),
                lambda: self.guard(lambda: self.run(action, planner(), masters=masters())))  # fmt: skip


class PlaceTab(Tab):
    """Place From Bounds: add or move top/bottom/_top/_bottom from the ink box."""

    def controls(self) -> None:
        self.anchor_rows = []
        for name, edge, on in model.BOUNDS_ANCHORS:
            line = QtGui.QHBoxLayout()
            tick = _check(self.widget, line, f"{name} at the {edge} edge", on)
            offset = _spin(self.widget, line, f"{name} offset", OFFSET_RANGE, 0)
            self.anchor_rows.append((name, edge, tick, offset))
            self.layout.addLayout(line)
        line = QtGui.QHBoxLayout()
        self.pair(line, "placement", self.planner, "place anchors")
        self.layout.addLayout(line)

    def wanted(self) -> list[tuple[str, str, float]]:
        return [(name, edge, float(_value(offset))) for name, edge, tick, offset in self.anchor_rows if _on(tick)]

    def planner(self) -> model.Planner:
        return self.studio.bounds_planner(self.wanted())


class AlignTab(Tab):
    """Center Horizontally, Snap To Metrics, Round To Grid and Optical Center."""

    def controls(self) -> None:
        centre = QtGui.QHBoxLayout()
        self.centre_names = _field(self.widget, centre, "Centre anchors", "top, bottom", CENTRE_DEFAULT)
        self.reference = _combo(self.widget, centre, "Reference", [label for label, _ in model.REFERENCES])
        centre.addWidget(QtGui.QLabel("Position %", self.widget))
        self.fraction = QtGui.QSlider(self.widget)
        self.fraction.setOrientation(QtCore.Qt.Horizontal)
        self.fraction.setAccessibleName("Position %")
        self.fraction.setRange(0, 100)
        self.fraction.setValue(FRACTION_DEFAULT)
        centre.addWidget(self.fraction)
        self.angle = _spin(self.widget, centre, "Italic angle", ANGLE_RANGE, 0)
        _button(self.widget, centre, "Use font italic angle", self.use_italic_angle)
        self.pair(centre, "centring", self.centre_planner, "centre anchors")
        self.layout.addLayout(centre)
        snap = QtGui.QHBoxLayout()
        self.snap_names = _field(self.widget, snap, "Snap anchors", "top", CLOUD_DEFAULT)
        self.metric = _combo(self.widget, snap, "Metric", [label for label, _ in model.METRICS], SNAP_METRIC_DEFAULT)
        self.snap_offset = _spin(self.widget, snap, "Snap offset", OFFSET_RANGE, 0)
        self.pair(snap, "snapping", self.snap_planner, "snap anchors")
        self.layout.addLayout(snap)
        grid = QtGui.QHBoxLayout()
        self.step = _spin(self.widget, grid, "Grid step", STEP_RANGE, STEP_DEFAULT)
        self.do_x = _check(self.widget, grid, "Round x", True)
        self.do_y = _check(self.widget, grid, "Round y", True)
        self.round_names = _field(self.widget, grid, "Round anchors", "blank rounds every anchor")
        self.pair(grid, "rounding", self.round_planner, "round anchors")
        self.layout.addLayout(grid)
        optical = QtGui.QHBoxLayout()
        optical.addWidget(QtGui.QLabel("Optical centre reads and writes the preview master only.", self.widget), 1)
        self.pair(optical, "optical centre", self.studio.optical_planner, "align top optically",
                  masters=lambda: [self.studio.master] if self.studio.master else None)  # fmt: skip
        self.layout.addLayout(optical)

    def use_italic_angle(self) -> float:
        angle = self.guard(self.studio.italic_angle)
        if angle is not False:
            self.angle.setValue(int(round(angle)))
        return angle

    def centre_planner(self) -> model.Planner:
        reference = model.REFERENCES[_get(self.reference.currentIndex)][1]
        fraction = _value(self.fraction) / 100
        return self.studio.centre_planner(model.parse_names(_text(self.centre_names)), reference, fraction,
                                          float(_value(self.angle)))  # fmt: skip

    def snap_planner(self) -> model.Planner:
        attribute = model.METRICS[_get(self.metric.currentIndex)][1]
        return self.studio.snap_planner(model.parse_names(_text(self.snap_names)), attribute,
                                        float(_value(self.snap_offset)))  # fmt: skip

    def round_planner(self) -> model.Planner:
        return self.studio.round_planner(_value(self.step), _on(self.do_x), _on(self.do_y),
                                         model.parse_names(_text(self.round_names)))  # fmt: skip


class RenameTab(Tab):
    """Rename Bulk and Delete By Name over the glyph list or the whole font."""

    def controls(self) -> None:
        rename = QtGui.QHBoxLayout()
        self.find = _field(self.widget, rename, "Find", "top")
        self.replace = _field(self.widget, rename, "Replace with", "top.alt")
        self.regex = _check(self.widget, rename, "Regular expression", False)
        self.scope = _combo(self.widget, rename, "Scope", SCOPES)
        self.pair(rename, "renaming", self.rename_planner, "rename anchors")
        self.layout.addLayout(rename)
        delete = QtGui.QHBoxLayout()
        _button(self.widget, delete, "List anchor names", self.list_names)
        self.census_list = QtGui.QListWidget(self.widget)
        self.census_list.setAccessibleName("Anchor names")
        delete.addWidget(self.census_list, 1)
        self.pair(delete, "deletion", self.delete_planner, "delete anchors")
        self.layout.addLayout(delete)

    def chosen(self) -> list[str]:
        return self.studio.font_glyphs() if _get(self.scope.currentIndex) == 1 else self.names()

    def rename_planner(self) -> model.Planner:
        return self.studio.rename_planner(_get(self.find.text), _get(self.replace.text), _on(self.regex))

    def list_names(self) -> dict[str, list[int]]:
        """Read-only census: every anchor name with editable and auto layer counts."""
        def go() -> dict[str, list[int]]:
            counts = self.studio.census(self.chosen(), all_masters=self.every_master())
            self.census_list.clear()
            for name, (editable, auto) in counts.items():
                item = QtGui.QListWidgetItem(f"{name}  ({editable} layers" + (f", {auto} auto" if auto else "") + ")")
                item.setData(QtCore.Qt.UserRole, name)
                item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
                item.setCheckState(QtCore.Qt.Unchecked)
                self.census_list.addItem(item)
            self.studio.say(f"{APP}: {len(counts)} anchor name(s) found; nothing written.")
            return counts

        return self.guard(go)

    def ticked(self) -> list[str]:
        items = [self.census_list.item(i) for i in range(_get(self.census_list.count))]
        return [str(item.data(QtCore.Qt.UserRole)) for item in items if _get(item.checkState) == QtCore.Qt.Checked]

    def delete_planner(self) -> model.Planner:
        return self.studio.delete_planner(self.ticked())


class CleanupTab(Tab):
    """Duplicates Finder and Remove Extraneous Mark Anchors."""

    def controls(self) -> None:
        duplicates = QtGui.QHBoxLayout()
        self.scope = _combo(self.widget, duplicates, "Duplicates scope", SCOPES)
        self.coincident = _check(self.widget, duplicates, "Also remove coincident anchors of other names", False)
        self.pair(duplicates, "duplicates", lambda: self.studio.duplicates_planner(_on(self.coincident)),
                  "remove duplicate anchors", masters=lambda: list(self.studio.masters) or None)  # fmt: skip
        self.layout.addLayout(duplicates)
        extra = QtGui.QHBoxLayout()
        duplicates.addWidget(QtGui.QLabel("Every master.", self.widget))
        extra.addWidget(QtGui.QLabel("Marks with _top lose bottom; marks with _bottom lose top. Every master.",
                                     self.widget), 1)  # fmt: skip
        self.pair(extra, "extraneous anchors", self.studio.extraneous_planner, "remove extraneous anchors",
                  masters=lambda: list(self.studio.masters) or None)  # fmt: skip
        self.layout.addLayout(extra)

    def chosen(self) -> list[str]:
        return self.studio.font_glyphs() if _get(self.scope.currentIndex) == 1 else self.names()


class OverlaysTab(Tab):
    """Cloud View, Duplicate Anchor Rings and the anchor table; reads only, never opens history."""

    WRITES = False

    def controls(self) -> None:
        self.clouds: dict[str, Any] = {}
        self.cloud_anchor = ""
        line = QtGui.QHBoxLayout()
        self.anchor = _field(self.widget, line, "Anchor name", "top", CLOUD_DEFAULT)
        _button(self.widget, line, "Show cloud", self.show_cloud)
        self.size = _combo(self.widget, line, "Handle size", [str(size) for size in model.HANDLE_SIZES], 1)
        _button(self.widget, line, "Show rings", self.show_rings)
        _button(self.widget, line, "Clear overlay", self.clear)
        _button(self.widget, line, "List anchors", self.list_anchors)
        self.summary = QtGui.QLabel("", self.widget)
        line.addWidget(self.summary, 1)
        self.layout.addLayout(line)
        self.anchor_table = fontui.glyph_table(list(ANCHOR_COLUMNS), self.widget)
        self.anchor_table.row_selected.connect(self.anchor_chosen)
        self.layout.addWidget(self.studio.shell.embed(self.anchor_table), 1)

    def _overlay(self, overlay: Any, anchors: Sequence[str]) -> None:
        preview = self.studio.preview
        if preview is not None:
            preview.set_overlay(overlay)
            preview.highlight(anchors=anchors)

    def refresh(self) -> None:
        super().refresh()
        if self.clouds:
            self._overlay(self.clouds.get(self.studio.master), [self.cloud_anchor])

    def show_cloud(self) -> list[tuple[str, str, float, float]]:
        def go() -> list[tuple[str, str, float, float]]:
            names = self.names()
            self.studio.set_glyphs(names)
            anchor = _text(self.anchor) or CLOUD_DEFAULT
            overlays, points = self.studio.cloud(anchor, names)
            self.clouds, self.cloud_anchor = overlays, anchor
            if names:
                self.studio.show_glyph(names[0])
            self._overlay(overlays.get(self.studio.master), [anchor])
            self.records = [(glyph, master, (master, anchor, model.point_text(x, y), "", ""))
                            for glyph, master, x, y in points]  # fmt: skip
            self.table.set_rows(self.records)
            spread = model.extremes([(x, y) for _, _, x, y in points])
            masters = len({master for _, master, _, _ in points})
            self.summary.setText(f"{len(points)} {anchor} anchor(s) on {masters} master(s)" + (f": {spread}" if spread else ""))
            return points

        return self.guard(go)

    def show_rings(self) -> list[tuple[str, str, Any]]:
        def go() -> list[tuple[str, str, Any]]:
            names = self.names()
            self.studio.set_glyphs(names)
            size = model.HANDLE_SIZES[_get(self.size.currentIndex)]
            shown = names[0] if names else ""
            overlay, found = self.studio.rings(shown, size, names)
            self.clouds = {}
            if shown:
                self.studio.show_glyph(shown)
            self._overlay(overlay, sorted({pin.name for glyph, _, pin in found if glyph == shown}))
            self.records = [(glyph, master, (master, pin.name, model.point_text(pin.x, pin.y), "", "stacked"))
                            for glyph, master, pin in found]  # fmt: skip
            self.table.set_rows(self.records)
            self.summary.setText(f"{len(found)} stacked anchor(s) in {len({g for g, _, _ in found})} glyph(s)")
            return found

        return self.guard(go)

    def list_anchors(self) -> list[tuple[str, str, str, float, float]]:
        """Fill the sortable anchor table: one row per anchor per master."""

        def go() -> list[tuple[str, str, str, float, float]]:
            names = self.names()
            self.studio.set_glyphs(names)
            rows = self.studio.anchor_rows(names)
            self.anchor_table.set_rows([(glyph, master, (master, name, x, y)) for glyph, master, name, x, y in rows])
            self.summary.setText(f"{len(rows)} anchor(s) in {len(set(names))} glyph(s)")
            return rows

        return self.guard(go)

    def anchor_chosen(self, name: str, layer: Any = None) -> None:
        """Show the chosen row's glyph on its master and highlight that anchor."""
        table = self.anchor_table
        index = table.view.currentIndex()
        if not name or index is None or not index.isValid():
            return
        anchor = table.rows[table.proxy.mapToSource(index).row()].values[1]
        self.clouds = {}
        self.row_chosen(name, layer)
        preview = self.studio.preview
        if preview is not None:
            preview.highlight(anchors=[anchor])

    def clear(self) -> None:
        self.clouds = {}
        self._overlay(None, ())
        self.summary.setText("")


TAB_CLASSES = (
    ("Place", PlaceTab),
    ("Align", AlignTab),
    ("Rename & delete", RenameTab),
    ("Clean-up", CleanupTab),
    ("Overlays", OverlaysTab),
)

__all__ = ["TAB_CLASSES", "AlignTab", "CleanupTab", "OverlaysTab", "PlaceTab", "RenameTab", "Tab", "records"]
