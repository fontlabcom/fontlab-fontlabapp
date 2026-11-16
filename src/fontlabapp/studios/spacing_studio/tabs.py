# this_file: src/fontlabapp/studios/spacing_studio/tabs.py
# SPDX-License-Identifier: Apache-2.0
"""The four Spacing Studio tabs: Sidebearings, Reference, Italic and Strings.

What: each tab is a plain Qt widget over the shared ``Studio`` state with the
same glyph row (names field, "Use font selection", preview master and "All
masters") and a sortable ``GlyphTable`` of the last plan or reading. Choosing
a row shows that glyph in the TMetrics preview (contract §1.8). Buttons name
their action. The comparison, offset preview and spacing strings only read.
Why: one window replaces ten Scriptmix/example spacing scripts (Phase D A2).
Used by ``fontlabapp.studios.spacing_studio`` (tab builders and ``show``).
"""

from collections.abc import Callable, Sequence
from typing import Any

from PythonQt import QtCore, QtGui

import fontlabapp.fontui as fontui

from . import APP, model
from .session import NO_FONT, Row, Studio

PLAN_COLUMNS = ("Glyph", "Master", "LSB", "RSB", "Advance", "Note")
ORIENTATIONS = ("Horizontal", "Vertical")
ALLOW_BASES_LABEL = "Edit bases of auto glyphs anyway"  # the absorbed scripts' opt-in, off by default


def _button(owner: Any, layout: Any, text: str, slot: Callable[[], Any]) -> Any:
    button = QtGui.QPushButton(text, owner)
    button.setAccessibleName(text)
    button.clicked.connect(lambda *args: slot())
    layout.addWidget(button)
    return button


def _field(owner: Any, layout: Any, label: str, placeholder: str = "") -> Any:
    layout.addWidget(QtGui.QLabel(label, owner))
    field = QtGui.QLineEdit(owner)
    field.setPlaceholderText(placeholder)
    field.setAccessibleName(label)
    layout.addWidget(field)
    return field


def _combo(owner: Any, layout: Any, label: str, items: Sequence[str]) -> Any:
    layout.addWidget(QtGui.QLabel(label, owner))
    box = QtGui.QComboBox(owner)
    box.setAccessibleName(label)
    box.addItems(list(items))
    layout.addWidget(box)
    return box


def _get(value: Any) -> Any:
    return value() if callable(value) else value


def _text(field: Any) -> str:
    return str(_get(field.text)).strip()


def _number(field: Any, label: str) -> float | None:
    """The field's number, None when blank; ValueError names the field otherwise."""
    text = _text(field)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        raise ValueError(f"{label} must be a number.") from None


def _names(text: str) -> list[str]:
    return [name for name in text.replace("/", " ").replace(",", " ").split() if name]


def _change(before: Any, after: Any) -> str:
    return f"{before:g}" if after is None or after == before else f"{before:g} → {after:g}"


class Tab:
    """A tab bound to the studio: glyph row, master row, the action area and a result table."""

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
        self.all_masters = QtGui.QCheckBox("All masters", self.widget)
        self.all_masters.setAccessibleName("All masters")
        masters.addWidget(self.all_masters)
        self.allow_bases = QtGui.QCheckBox(ALLOW_BASES_LABEL, self.widget)
        self.allow_bases.setAccessibleName(ALLOW_BASES_LABEL)
        self.allow_bases.setVisible(self.WRITES)
        masters.addWidget(self.allow_bases)
        self.write_note = QtGui.QLabel("", self.widget)
        masters.addWidget(self.write_note, 1)
        self.layout.addLayout(masters)
        self.controls()
        self.table = fontui.glyph_table(list(self.COLUMNS), self.widget, layer_column=True)
        self.table.row_selected.connect(self.row_chosen)
        self.layout.addWidget(studio.shell.embed(self.table), 1)
        studio.views.append(self.refresh)

    COLUMNS: Sequence[str] = PLAN_COLUMNS
    WRITES = True  # writing tabs show the "Edit bases of auto glyphs anyway" opt-in

    def controls(self) -> None:  # pragma: no cover - overridden
        pass

    # Shared state ----------------------------------------------------------
    def names(self) -> list[str]:
        return _names(_text(self.glyphs_field))

    def every_master(self) -> bool:
        return bool(_get(self.all_masters.isChecked))

    def bases_allowed(self) -> bool:
        return bool(self.WRITES and _get(self.allow_bases.isChecked))

    def use_selection(self) -> list[str]:
        names = self.studio.use_selection()
        self.glyphs_field.setText(" ".join(names))
        if not names:
            self.studio.say(f"{APP}: {'Select glyphs in the Font window first.'}")
        return names

    def refresh(self) -> None:
        studio = self.studio
        self.master_box.blockSignals(True)
        self.master_box.clear()
        self.master_box.addItems(list(studio.masters))
        if studio.master in studio.masters:
            self.master_box.setCurrentIndex(studio.masters.index(studio.master))
        self.master_box.blockSignals(False)
        self.write_note.setText(f"Writes go to {studio.master} unless All masters is on." if studio.master else NO_FONT)
        self.table.set_rows(self.records)

    def refresh_sources(self, records: Sequence[Any]) -> None:
        """Remeasure displayed identities; proposed writes require explicit Preview."""
        if [self.master_box.itemText(i) for i in range(self.master_box.count())] != self.studio.masters:
            Tab.refresh(self)
        refreshed = []
        for name, master, _ in records:
            layer = self.studio.layer(name, master)
            if layer is None:
                raise ValueError(f"{name} has no layer {master}.")
            before = self.studio.metrics(name, master)
            offset = getattr(self, "_offset", None)
            if offset is not None:
                _, left, right, width = model.offset_rows([(name, before)], offset)[0]
                values = (left, right, width, f"offset {offset:+d}")
            else:
                values = ((str(before.lsb), str(before.rsb), f"{before.width:g}") if before else
                          ("", "", f"{layer.advanceWidth:g}"))
                values += ("Current metrics; preview again." if self.WRITES else "",)
            refreshed.append((name, master, values))
        self.records = refreshed
        self.table.set_rows(refreshed)

    def _master_changed(self) -> None:
        name = _get(self.master_box.currentText)
        if name and name != self.studio.master:
            self.studio.choose_master(name)
            self.refresh()

    def row_chosen(self, name: str, layer: Any = None) -> None:
        preview = self.studio.preview
        if preview is None or not name:
            return
        if layer and layer != self.studio.master and layer in self.studio.masters:
            self.studio.choose_master(layer)
        preview.set_text("/" + name)

    def show_rows(self, rows: Sequence[Row]) -> None:
        records = []
        for row in rows:
            before, plan = row.before, row.plan
            if before is None:
                values: tuple[Any, ...] = ("", "", "", row.note)
            else:
                values = (
                    _change(before.lsb, plan and plan.lsb),
                    _change(before.rsb, plan and plan.rsb),
                    _change(before.width, plan and plan.width),
                    row.note,
                )
            records.append((row.glyph, row.master, values))
        self.records = records
        self.table.set_rows(records)

    def run(self, action: str, planner: model.Planner, *, masters: Sequence[str] | None = None) -> bool:
        """Write ``planner`` to the named glyphs as one labelled step; show the plan."""
        names = self.names()
        self.studio.set_glyphs(names)
        done = self.studio.apply(action, planner, names, all_masters=self.every_master(), masters=masters,
                                  allow_bases=self.bases_allowed())  # fmt: skip
        self.show_rows(self.studio.rows)
        if names and self.studio.preview is not None:
            self.studio.preview.set_text("/" + "/".join(names))
        return done

    def guard(self, action: Callable[[], Any]) -> Any:
        """Run ``action``; a ValueError from a field becomes the status line."""
        try:
            return action()
        except ValueError as error:
            self.studio.say(f"{APP}: {error}")
            return False


class SidebearingsTab(Tab):
    """Metrics Tuner, Equalize Sidebearings and Centre Glyph, plus the hint opt-in."""

    def controls(self) -> None:
        tune = QtGui.QHBoxLayout()
        self.operation = _combo(self.widget, tune, "Operation", [label for label, _ in model.OPERATIONS])
        self.lsb_field = _field(self.widget, tune, "LSB", "blank keeps it")
        self.rsb_field = _field(self.widget, tune, "RSB", "blank keeps it")
        self.lsb_field.setText("0")
        self.rsb_field.setText("0")
        self._scaling = False
        self._scale_defaults: set[str] = set()
        self.units = QtGui.QLabel("units", self.widget)
        tune.addWidget(self.units)
        self.operation.currentIndexChanged.connect(lambda *args: self.tune_mode())
        _button(self.widget, tune, "Apply to sidebearings", self.tune)
        self.layout.addLayout(tune)
        equal = QtGui.QHBoxLayout()
        self.rule = _combo(self.widget, equal, "Equalize", [label for label, _ in model.EQUALIZE_RULES])
        _button(self.widget, equal, "Equalize sidebearings", self.equalize)
        self.layout.addLayout(equal)
        centre = QtGui.QHBoxLayout()
        self.width_mode = _combo(self.widget, centre, "Width", [label for label, _ in model.WIDTH_MODES])
        self.width_field = _field(self.widget, centre, "Width value", str(model.WIDTH_DEFAULT))
        self.width_field.setEnabled(False)
        self.width_mode.currentIndexChanged.connect(lambda *args: self.centre_mode())
        _button(self.widget, centre, "Centre in advance", self.centre)
        self.layout.addLayout(centre)
        hints = QtGui.QHBoxLayout()
        hints.addWidget(QtGui.QLabel("Hinted layers are skipped when the outline moves.", self.widget), 1)
        _button(self.widget, hints, "Remove PostScript hints", self.remove_hints)
        self.layout.addLayout(hints)

    def tune_mode(self) -> None:
        """Swap neutral values while preserving typed numbers and blank keep fields."""
        scale = model.OPERATIONS[_get(self.operation.currentIndex)][1] == "scale"
        self.units.setText("%" if scale else "units")
        if scale == self._scaling:
            return
        self._scaling = scale
        for name in ("lsb_field", "rsb_field"):
            field = getattr(self, name)
            try:
                number = float(_text(field))
            except ValueError:
                continue
            if scale and number == 0:
                self._scale_defaults.add(name)
                field.setText("100")
            elif not scale and name in self._scale_defaults and number == 100:
                field.setText("0")
        if not scale:
            self._scale_defaults.clear()

    def tune(self) -> bool:
        def go() -> bool:
            label, mode = model.OPERATIONS[_get(self.operation.currentIndex)]
            lsb, rsb = _number(self.lsb_field, "LSB"), _number(self.rsb_field, "RSB")
            if lsb is None and rsb is None:
                raise ValueError("Type an LSB or RSB value first.")
            return self.run(f"{mode} sidebearings", lambda n, before, layer, m: model.tune(before, mode, lsb, rsb))

        return self.guard(go)

    def equalize(self) -> bool:
        rule = model.EQUALIZE_RULES[_get(self.rule.currentIndex)][1]
        return self.run("equalize sidebearings", lambda n, before, layer, m: model.equalize(before, rule))

    def centre_mode(self) -> None:
        """Restore the original neutral Add and positive Set-width defaults."""
        mode = model.WIDTH_MODES[_get(self.width_mode.currentIndex)][1]
        self.width_field.setEnabled(mode != "keep")
        if mode == "add":
            self.width_field.setText("0")
        elif mode == "set":
            try:
                value = float(_text(self.width_field))
            except ValueError:
                value = 0
            if value <= 0:
                self.width_field.setText(str(model.WIDTH_DEFAULT))

    def centre(self) -> bool:
        def go() -> bool:
            mode = model.WIDTH_MODES[_get(self.width_mode.currentIndex)][1]
            value = _number(self.width_field, "Width value")
            if value is None:
                value = 0 if mode == "add" else model.WIDTH_DEFAULT
            return self.run("centre", lambda n, before, layer, m: model.centred(before, mode, value))

        return self.guard(go)

    def remove_hints(self) -> int:
        names = self.names()
        removed = self.studio.remove_hints(names, all_masters=self.every_master())
        if removed:
            self.studio.say(f"{APP}: removed PostScript hints from {removed} layer{'s' if removed != 1 else ''}.")
        return removed


class ReferenceTab(Tab):
    """Copy Metrics From Reference, Sync Sidebearings and Layer Metric Comparison (read-only)."""

    def controls(self) -> None:
        copy = QtGui.QHBoxLayout()
        self.reference_field = _field(self.widget, copy, "Reference glyph", "H")
        self.completer = QtGui.QCompleter(self.widget)
        self.completion_model = QtGui.QStringListModel(self.completer)
        self.completer.setModel(self.completion_model)
        self.completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.completer.setFilterMode(QtCore.Qt.MatchContains)
        self.reference_field.setCompleter(self.completer)
        self.copy_mode = _combo(self.widget, copy, "Copy", [label for label, _ in model.COPY_MODES])
        self.offset_field = _field(self.widget, copy, "Offset", "0")
        _button(self.widget, copy, "Copy from reference", self.copy)
        self.layout.addLayout(copy)
        sync = QtGui.QHBoxLayout()
        self.sync_master = _combo(self.widget, sync, "Reference master", [])
        self.sync_rule = _combo(self.widget, sync, "Sync", [label for label, _ in model.SYNC_RULES])
        _button(self.widget, sync, "Sync sidebearings", self.sync)
        self.layout.addLayout(sync)
        compare = QtGui.QHBoxLayout()
        self.measure = _combo(self.widget, compare, "Measure", list(model.MEASURES))
        self.compare_mode = _combo(self.widget, compare, "Against", list(model.COMPARE_MODES))
        self.compare_glyph = _field(self.widget, compare, "Compare to glyph", "first row")
        self.compare_layer = _field(self.widget, compare, "Compare to layer", "preview master")
        _button(self.widget, compare, "Compare layers", self.compare)
        _button(self.widget, compare, "Copy table", self.copy_table)
        self.layout.addLayout(compare)

    def fill_reference_names(self) -> None:
        """Keep completion current; a failed font-list read remains visible."""
        from fontlabapp.core.scripting import names_font_glyphs

        try:
            self.studio.package()
            names = [name for name, _ in names_font_glyphs()]
            hint = "Glyph name, e.g. H or n"
        except (ValueError, RuntimeError, TimeoutError) as error:
            names = []
            hint = f"Glyph list not read ({error}); type a glyph name"
        self.completion_model.setStringList(names)
        self.reference_field.setPlaceholderText(hint)

    def use_selection(self) -> list[str]:
        self.fill_reference_names()
        return super().use_selection()

    def refresh(self) -> None:
        super().refresh()
        self.fill_reference_names()
        chosen = _get(self.sync_master.currentText)
        self.sync_master.blockSignals(True)
        self.sync_master.clear()
        self.sync_master.addItems(list(self.studio.masters))
        if chosen in self.studio.masters:
            self.sync_master.setCurrentIndex(self.studio.masters.index(chosen))
        self.sync_master.blockSignals(False)

    def copy(self) -> bool:
        def go() -> bool:
            reference = _text(self.reference_field)
            if not reference:
                raise ValueError("Type a reference glyph first.")
            offset = _number(self.offset_field, "Offset") or 0
            if offset != int(offset):
                raise ValueError("Offset must be a whole number.")
            mode = model.COPY_MODES[_get(self.copy_mode.currentIndex)][1]
            names = [name for name in self.names() if name != reference]
            if not names:
                raise ValueError("Choose glyphs other than the reference.")
            self.glyphs_field.setText(" ".join(names))
            return self.run(f"copy metrics from {reference} to", self.studio.reference_planner(reference, mode, int(offset)))

        return self.guard(go)

    def sync(self) -> bool:
        def go() -> bool:
            reference = _get(self.sync_master.currentText)
            if not reference:
                raise ValueError(NO_FONT)
            proportional = model.SYNC_RULES[_get(self.sync_rule.currentIndex)][1]
            targets = self.studio.sync_targets(reference, self.every_master())
            return self.run("sync sidebearings", self.studio.sync_planner(reference, proportional), masters=targets)

        return self.guard(go)

    def show_rows(self, rows: Sequence[Row]) -> None:
        self.comparison = []
        self._comparison_request = None
        super().show_rows(rows)

    def refresh_sources(self, records: Sequence[Any]) -> None:
        request = getattr(self, "_comparison_request", None)
        if request is None:
            super().refresh_sources(records)
        else:
            self._show_comparison(self.studio.comparison(*request, all_masters=True), request[0])

    def _show_comparison(self, rows: Any, which: str) -> None:
        self.records = [(name, master, (which, value, against, "")) for name, master, value, against in rows]
        self.table.set_rows(self.records)
        self.comparison = rows

    COMPARE_COLUMNS = ("Glyph", "Master", "Value", "Against reference")

    def compare(self) -> list[tuple[str, str, str, str]]:
        """Read every chosen layer's measurement; show it in the table. No writes."""
        which = model.MEASURES[_get(self.measure.currentIndex)]
        mode = model.COMPARE_MODES[_get(self.compare_mode.currentIndex)]
        glyph = _text(self.compare_glyph)
        reference = (glyph, _text(self.compare_layer)) if glyph else None
        self.comparison, self.records, self._comparison_request = [], [], None
        self.table.set_rows([])
        request = (which, reference, mode, self.names())
        try:
            rows = self.studio.comparison(*request, all_masters=True)
        except (ValueError, KeyError) as error:
            self.studio.say(f"{APP}: {error}")
            return []
        self._comparison_request = request
        self._show_comparison(rows, which)
        self.studio.say(f"{APP}: compared {which.lower()} on {len(rows)} layers ({mode.lower()}).")
        return rows

    comparison: list[tuple[str, str, str, str]] = []

    def copy_table(self) -> str:
        """Copy the last comparison as tab-separated text to the clipboard."""
        lines = ["\t".join(self.COMPARE_COLUMNS), *("\t".join(row) for row in self.comparison)]
        text = "\n".join(lines)
        if not self.comparison:
            self.studio.say(f"{APP}: Compare layers first.")
            return ""
        QtGui.QApplication.clipboard().setText(text)
        self.studio.say(f"{APP}: copied {len(self.comparison)} rows.")
        return text


class ItalicTab(Tab):
    """Italic Spacing: sidebearings measured on the de-slanted outline."""

    def controls(self) -> None:
        row = QtGui.QHBoxLayout()
        self.angle_field = _field(self.widget, row, "Italic angle", "font angle")
        self.pivot_field = _field(self.widget, row, "Slant pivot height", "half x-height")
        self.mode = _combo(self.widget, row, "Operation", [label for label, _ in model.ITALIC_MODES])
        self.lsb_field = _field(self.widget, row, "Italic LSB", "blank keeps it")
        self.rsb_field = _field(self.widget, row, "Italic RSB", "blank keeps it")
        _button(self.widget, row, "Apply italic spacing", self.apply)
        self.layout.addLayout(row)

    def refresh(self) -> None:
        super().refresh()
        if self.studio.masters and not _text(self.angle_field):
            try:
                angle, pivot = self.studio.italic_defaults()
            except ValueError:
                return
            self.angle_field.setText(f"{angle:g}")
            self.pivot_field.setText(str(pivot))

    def apply(self) -> bool:
        def go() -> bool:
            angle = _number(self.angle_field, "Italic angle")
            pivot = _number(self.pivot_field, "Slant pivot height")
            if angle is None or pivot is None:
                angle_default, pivot_default = self.studio.italic_defaults()
                angle = angle_default if angle is None else angle
                pivot = pivot_default if pivot is None else pivot
            lsb, rsb = _number(self.lsb_field, "Italic LSB"), _number(self.rsb_field, "Italic RSB")
            if lsb is None and rsb is None:
                raise ValueError("Type an italic LSB or RSB value first.")
            mode = model.ITALIC_MODES[_get(self.mode.currentIndex)][1]
            return self.run("italic spacing", self.studio.italic_planner(angle, pivot, mode, lsb, rsb))

        return self.guard(go)


class StringsTab(Tab):
    """Spacing String Preview, Sidebearing Offset Preview and the TMetrics window (all read-only)."""

    COLUMNS = ("Glyph", "Master", "LSB", "RSB", "Advance", "Note")
    WRITES = False

    def controls(self) -> None:
        row = QtGui.QHBoxLayout()
        self.text_field = _field(self.widget, row, "Spacing strings", model.DEFAULT_STRINGS)
        _button(self.widget, row, "Show strings", self.show_strings)
        _button(self.widget, row, "Open TMetrics window", self.open_window)
        self.layout.addLayout(row)
        # Sidebearing Offset Preview's editors: minimum, maximum, offset, orientation, two inverts.
        offset = QtGui.QHBoxLayout()
        boxes = []
        for label, initial in (("Minimum offset", 0), ("Maximum offset", 20), ("Preview offset", 5)):
            box = QtGui.QSpinBox(self.widget)
            box.setAccessibleName(label)
            box.setRange(-model.OFFSET_LIMIT, model.OFFSET_LIMIT)
            box.setValue(initial)
            offset.addWidget(QtGui.QLabel(label, self.widget))
            offset.addWidget(box)
            boxes.append(box)
        self.minimum_box, self.maximum_box, self.offset_box = boxes
        _button(self.widget, offset, "Preview offset", self.preview_offset)
        self.layout.addLayout(offset)
        slider_row = QtGui.QHBoxLayout()
        self.slider = QtGui.QSlider(self.widget)
        self.slider.setAccessibleName("Offset slider")
        slider_row.addWidget(self.slider, 1)
        self.orientation = QtGui.QComboBox(self.widget)
        self.orientation.setAccessibleName("Slider orientation")
        self.orientation.addItems(list(ORIENTATIONS))
        slider_row.addWidget(self.orientation)
        self.invert_appearance = QtGui.QCheckBox("Invert appearance", self.widget)
        self.invert_keys = QtGui.QCheckBox("Invert key bindings", self.widget)
        for box in (self.invert_appearance, self.invert_keys):
            box.setAccessibleName(_get(box.text))
            slider_row.addWidget(box)
        self.layout.addLayout(slider_row)
        self.orient(0)
        self._bounds()
        self.minimum_box.valueChanged.connect(lambda *args: self._bounds())
        self.maximum_box.valueChanged.connect(lambda *args: self._bounds())
        self.offset_box.valueChanged.connect(lambda *args: self._follow(int(_get(self.offset_box.value))))
        self.slider.valueChanged.connect(lambda *args: self._follow(int(_get(self.slider.value))))
        self.orientation.currentIndexChanged.connect(lambda *args: self.orient(int(_get(self.orientation.currentIndex))))
        self.invert_appearance.toggled.connect(lambda *args: self.slider.setInvertedAppearance(
            bool(_get(self.invert_appearance.isChecked))))  # fmt: skip
        self.invert_keys.toggled.connect(lambda *args: self.slider.setInvertedControls(
            bool(_get(self.invert_keys.isChecked))))  # fmt: skip

    def orient(self, index: int) -> None:
        """Horizontal or Vertical offset slider, as in Sidebearing Offset Preview."""
        from PythonQt import QtCore

        self.slider.setOrientation(QtCore.Qt.Horizontal if index == 0 else QtCore.Qt.Vertical)

    def bounds(self) -> tuple[int, int]:
        low = int(_get(self.minimum_box.value))
        return low, max(low, int(_get(self.maximum_box.value)))

    def _bounds(self) -> None:
        """Raise a maximum below the minimum, range the slider, and clamp the offset."""
        low, high = self.bounds()
        if int(_get(self.maximum_box.value)) != high:
            self.maximum_box.setValue(high)
        self.slider.setRange(low, high)
        self._follow(int(_get(self.offset_box.value)))

    def _follow(self, value: int) -> None:
        """Keep the offset editor and slider on one value inside minimum..maximum."""
        low, high = self.bounds()
        bounded = max(low, min(high, value))
        for control in (self.offset_box, self.slider):
            if int(_get(control.value)) != bounded:
                control.blockSignals(True)
                control.setValue(bounded)
                control.blockSignals(False)

    def text(self) -> str:
        return _text(self.text_field) or model.DEFAULT_STRINGS

    def show_strings(self) -> list[tuple[str, str, str, str]]:
        """Show the strings in the preview and list each glyph's current spacing. No writes."""
        self._offset = None
        self.offset_snapshot = None
        text = self.text()
        try:
            rows = self.studio.string_rows(text)
        except ValueError as error:
            self.studio.say(f"{APP}: {error}")
            return []
        if self.studio.preview is not None:
            self.studio.preview.set_text(text)
        master = self.studio.master
        self.records = [(name, master, (lsb, rsb, width, "")) for name, lsb, rsb, width in rows]
        self.table.set_rows(self.records)
        return rows

    def preview_offset(self) -> list[tuple[str, str, str, str]]:
        """Show LSB+offset and RSB−offset for the glyphs; the advance stays. No writes."""
        offset = int(_get(self.offset_box.value))
        try:
            names = self.names() or list(dict.fromkeys(self.studio.names_in(self.text())))
            rows = self.studio.offset_preview(offset, names)
        except ValueError as error:
            self.studio.say(f"{APP}: {error}")
            return []
        self._offset = offset
        self.offset_snapshot = None
        master = self.studio.master
        self.records = [(name, master, (lsb, rsb, width, f"offset {offset:+d}")) for name, lsb, rsb, width in rows]
        self.table.set_rows(self.records)
        self.studio.say(f"{APP}: preview only; offset {offset:+d} is not applied.")
        return rows

    def open_window(self) -> Any:
        """Open the standalone TMetrics window over the same font and strings."""
        font = self.studio.font()
        if font is None:
            self.studio.say(NO_FONT)
            return None
        return fontui.metrics_window(font, self.text(), parent=None)


TAB_CLASSES: Sequence[tuple[str, type[Tab]]] = (
    ("Sidebearings", SidebearingsTab),
    ("Reference", ReferenceTab),
    ("Italic", ItalicTab),
    ("Strings", StringsTab),
)


__all__ = ["ItalicTab", "PLAN_COLUMNS", "ReferenceTab", "SidebearingsTab", "StringsTab", "TAB_CLASSES", "Tab"]
