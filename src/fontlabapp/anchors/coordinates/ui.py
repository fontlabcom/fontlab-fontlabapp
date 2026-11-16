# this_file: src/fontlabapp/anchors/coordinates/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Complete original coordinate panels on the guarded owned Masters lifecycle."""

from typing import Any

import fontlabapp.anchors.coordinates.model as api
import fontlabapp.anchors.edit as edits
from fontlabapp import _native
from fontlabapp.masters.inspect.ui import MastersDialog, QtCore, QtGui, make_table
from fontlabapp.anchors.inspect.model import font_glyph_names, selected_glyphs
from fontlabapp.masters.inspect.model import muted


class CoordinateDialog(MastersDialog):
    """Bind original controls, complete raw source and a preconstructed operation."""

    WIDTH, HEIGHT = 560, 220

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent, self.TITLE, self.KEY)

    def build(self) -> None:
        self.clear_initial_state()
        self.setMinimumWidth(self.WIDTH)
        self.scope = QtGui.QComboBox()
        self.scope.addItem("Current master ()")
        self.scope.addItem("All masters (0)")
        self.build_controls()
        self.table = make_table(self.HEADERS, self.HEIGHT)
        self.table.setWordWrap(False)
        self.root.addWidget(self.table, 1)
        self.rebuild_label = QtGui.QLabel()
        self.blocker_label = QtGui.QLabel()
        for label in (self.rebuild_label, self.blocker_label):
            label.setWordWrap(True)
            label.setStyleSheet(f"color: {muted(self)};")
            label.setVisible(False)
            self.root.addWidget(label)
        self._connect(self.scope.currentIndexChanged, lambda *args: self.refresh())

    def watch(self, signal: Any) -> None:
        self._connect(signal, lambda *args: self.refresh())

    def clear_initial_state(self) -> None:
        self.glyphs, self.masters, self.current_master = [], [], ""
        self._selected_names, self._all_names, self._source_names = [], [], []
        self._prepared, self._options, self.last_result = None, None, None
        self.rebuild_key, self.rebuilds, self._skipped = None, [], []
        self._blocker = ""

    def load_initial(self) -> None:
        if self.package is None:
            return
        self.glyphs = selected_glyphs(self.package)
        self._selected_names = [glyph.name for glyph in self.glyphs]
        self._all_names = font_glyph_names()
        self.masters, self.current_master = (
            list(self.package.masters),
            self.package.master,
        )
        blocked = self.scope.blockSignals(True)
        try:
            self.scope.setItemText(0, f"Current master ({self.current_master})")
            self.scope.setItemText(1, f"All masters ({len(self.masters)})")
        finally:
            self.scope.blockSignals(blocked)
        angle = getattr(self, "angle", None)
        if angle is not None:
            blocked = angle.blockSignals(True)
            try:
                angle.setValue(edits.finite(self.package.italicAngle_value or 0))
            finally:
                angle.blockSignals(blocked)

    def capture_scope(self) -> None:
        if self.package is None or not self._selected_names:
            return
        affected = edits._affected(
            set(self._selected_names), edits.dependency_values(self.package)
        )
        self._source_names = [name for name in self._all_names if name in affected]

    def source_values(self, *, cached: bool = False) -> Any:
        if self.package is None:
            return None
        if font_glyph_names() != self._all_names:
            raise ValueError("Font glyph order changed; reopen this tool.")
        if [
            glyph.name for glyph in selected_glyphs(self.package)
        ] != self._selected_names:
            raise ValueError("Selection changed; reopen this tool.")
        metrics = []
        for master in self.masters:
            values = _native("fontlab").FontMetrics(self.package, master)
            metrics.append(
                (
                    master,
                    tuple(
                        edits.finite(getattr(values, attribute))
                        for _, attribute in api.METRICS
                        if attribute is not None
                    ),
                )
            )
        return (
            edits.source_values(self.package, self._source_names, self.masters),
            edits.finite(self.package.italicAngle_value or 0),
            tuple(metrics),
        )

    def option_values(self) -> tuple:
        return self.scope.currentIndex, self.names.text, self.settings()

    def ensure_snapshot(self, *, options: bool = True) -> None:
        try:
            super().ensure_snapshot()
            if options and self.option_values() != self._options:
                raise ValueError("Options changed since preview; refresh this tool.")
        except Exception:
            self.invalidate()
            raise

    def show_rebuilds(self) -> None:
        key = tuple(sorted(self._selected_names))
        if self.rebuild_key == key:
            return
        self.rebuild_key = key
        self.rebuilds = []
        for name in self._all_names:
            glyph = self.package.findName(name)
            if glyph is None or glyph.isNull:
                raise ValueError("Glyph source changed; reopen this tool.")
            layers = [api.layer_of(glyph, master) for master in self.masters]
            if any(
                layer is not None
                and layer.autoLayer
                and any(
                    shape.isComponent and shape.shapeData.componentGlyph in key
                    for shape in layer.shapes
                )
                for layer in layers
            ):
                self.rebuilds.append(name)
        shown = ", ".join(self.rebuilds[:8]) + (
            f" +{len(self.rebuilds) - 8} more" if len(self.rebuilds) > 8 else ""
        )
        self.rebuild_label.setText(
            "FontLab will rebuild the auto composites built on these glyphs: "
            + shown
            + ". Their anchors and locks may change."
            if shown
            else ""
        )
        self.rebuild_label.setVisible(bool(shown))

    def describe(self) -> None:
        if self.package is None:
            self.subtitle.setText("Open a font first.")
        elif not self.glyphs:
            self.subtitle.setText(
                "Select glyphs in the Font window, then run this script again."
            )
        else:
            count = len(self.glyphs)
            shown = ", ".join(self._selected_names[:8]) + (" …" if count > 8 else "")
            text = f"{count} glyph{'s' if count != 1 else ''}: {shown}"
            if self.KEY == "anchors_center_horizontally":
                text += f". Font italic angle {self.package.italicAngle_value or 0}°."
            elif self.KEY == "anchors_snap_to_metrics":
                text = "Anchor heights of " + text
            self.subtitle.setText(text)

    def fill_rows(self, rows: list) -> None:
        ink = QtGui.QBrush(QtGui.QColor(self.palette.color(QtGui.QPalette.WindowText)))
        accent = QtGui.QBrush(QtGui.QColor(self.palette.color(QtGui.QPalette.Link)))
        self.table.setRowCount(len(rows))
        for row, (cells, changed) in enumerate(rows):
            for column, text in enumerate(cells):
                item = QtGui.QTableWidgetItem(str(text))
                item.setForeground(ink)
                if column >= 2:
                    item.setTextAlignment(
                        int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                    )
                if changed and column == len(cells) - 1:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    item.setForeground(accent)
                self.table.setItem(row, column, item)

    def collect(self) -> tuple[list, list]:
        rows, jobs, skipped = [], [], []
        for glyph in self.glyphs:
            for master in self.chosen_masters():
                layer = api.layer_of(glyph, master)
                if layer is None:
                    continue
                moves, auto_pending = [], False
                for name, old, new in self.plan(layer, master):
                    cells, changed = self.render_row(old, new, bool(layer.autoLayer))
                    rows.append(((f"{glyph.name} · {master}", name, *cells), changed))
                    if new is None:
                        continue
                    axes = self.axis_flags()
                    point = (
                        new
                        if isinstance(new, tuple)
                        else (new, old[1])
                        if axes[0]
                        else (old[0], new)
                    )
                    if point == old:
                        continue
                    if layer.autoLayer:
                        auto_pending = True
                        continue
                    pins = [pin for pin in layer.anchors if pin.name == name]
                    if len(pins) != 1:
                        self._blocker = (
                            "Duplicate anchor names; resolve duplicates before moving."
                        )
                        continue
                    raw = edits.raw_point(pins[0])
                    moves.append(
                        (
                            pins[0],
                            tuple(
                                point[i] if axes[i] and point[i] != old[i] else raw[i]
                                for i in (0, 1)
                            ),
                        )
                    )
                if moves:
                    jobs.append((glyph, master, moves))
                if auto_pending:
                    skipped.append(f"{glyph.name}/{master}")
        self._skipped = skipped
        return rows, jobs

    def refresh(self) -> None:
        try:
            self.prepare_initial()
            self.check_binding()
            if self._snapshot_valid:
                self.ensure_snapshot(options=False)
            self._snapshot_valid, self._prepared, self._blocker = False, None, ""
            self.capture_scope()
            before, options = self.source_values(), self.option_values()
            self.describe()
            self.show_rebuilds()
            self.before_rows()
            rows, jobs = self.collect()
            self.rows = rows
            self.fill_rows(rows)
            pending = sum(changed for _, changed in rows)
            self.apply_button.setEnabled(pending > 0)
            self.set_pending_status(pending, bool(rows))
            if self.package is not None and not self._blocker:
                try:
                    self._prepared = edits.prepare_point_moves(self.package, jobs)
                except ValueError as error:
                    self._blocker = str(error)
            self.blocker_label.setText(self._blocker)
            self.blocker_label.setVisible(bool(self._blocker))
            if self._blocker:
                self.apply_button.setEnabled(False)
                self.status.setText(f"{self.ACTION} unavailable")
                self.adjustSize()
            self.check_binding()
            if before != self.source_values() or options != self.option_values():
                raise ValueError("Source changed during preview; reopen this tool.")
            self._source, self._options = before, options
            self._display_masters, self._display_master = (
                tuple(self.masters),
                self.current_master,
            )
            self._snapshot_valid, self._scanned_id = (
                self.package is not None,
                self._bound_id,
            )
            self.last_error = ""
        except Exception:
            self.invalidate()
            raise

    def before_rows(self) -> None:
        """Optional original value label before the shared layer scan."""

    def set_pending_status(self, count: int, rows: bool) -> None:
        self.status.setText(
            f"{count} anchor{'s' if count != 1 else ''} to move"
            if rows
            else "No anchors with these names on the selected glyphs"
        )

    def apply(self) -> None:
        try:
            self.ensure_snapshot()
            if self._blocker or self._prepared is None:
                raise ValueError(
                    self._blocker or "Results are incomplete; refresh this tool."
                )
            result = dict(
                edits.apply_point_moves(self._prepared, self.TITLE),
                skipped=list(self._skipped),
            )
            self._snapshot_valid = False
            self.refresh()
            self.last_result = result
            note = (
                f" · {len(result['skipped'])} auto layers skipped"
                if result["skipped"]
                else ""
            )
            self.status.setText(
                f"{self.VERB} {result['anchors']} anchors on {result['layers']} layers{note}"
            )
        except Exception as error:
            self.invalidate()
            self.show_error(error)
            raise

    def invalidate(self) -> None:
        super().invalidate()
        for name in ("rebuild_label", "blocker_label"):
            label = getattr(self, name, None)
            if label is not None:
                label.setText("")
                label.setVisible(False)
        values = getattr(self, "values", None)
        if values is not None:
            values.setText("")


class CenterAnchors(CoordinateDialog):
    TITLE, KEY = "Center Anchors Horizontally", "anchors_center_horizontally"
    ACTION, VERB = "Apply", "Moved"
    HEADERS = ("Glyph · master", "Anchor", "x, y", "New x")

    def build_controls(self) -> None:
        form = self.form()
        self.names = QtGui.QLineEdit("top, bottom")
        self.names.setPlaceholderText("anchor names, comma-separated")
        self.reference = QtGui.QComboBox()
        for label, _ in api.REFERENCES:
            self.reference.addItem(label)
        self.position = QtGui.QSlider(QtCore.Qt.Horizontal)
        self.position.setRange(0, 100)
        self.position.setValue(50)
        self.position.setTickPosition(QtGui.QSlider.TicksBelow)
        self.position.setTickInterval(25)
        self.position_label = QtGui.QLabel()
        self.position_label.setMinimumWidth(48)
        self.position_label.setAlignment(
            int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        )
        self.angle = QtGui.QDoubleSpinBox()
        self.angle.setRange(-45, 45)
        self.angle.setDecimals(1)
        self.angle.setSuffix("°")
        self.angle.setAlignment(QtCore.Qt.AlignRight)
        self.angle.setStyleSheet(
            f"color: {QtGui.QColor(self.palette.color(QtGui.QPalette.WindowText)).name()};"
        )
        form.addWidget(QtGui.QLabel("Anchors"), 0, 0)
        form.addWidget(self.names, 0, 1, 1, 2)
        form.addWidget(QtGui.QLabel("Centre of"), 1, 0)
        form.addWidget(self.reference, 1, 1, 1, 2)
        form.addWidget(QtGui.QLabel("Position"), 2, 0)
        form.addWidget(self.position, 2, 1)
        form.addWidget(self.position_label, 2, 2)
        form.addWidget(QtGui.QLabel("Italic angle"), 3, 0)
        form.addWidget(self.angle, 3, 1, 1, 2)
        form.addWidget(QtGui.QLabel("Masters"), 4, 0)
        form.addWidget(self.scope, 4, 1, 1, 2)
        form.setColumnStretch(1, 1)
        for signal in (
            self.names.textChanged,
            self.reference.currentIndexChanged,
            self.position.valueChanged,
            self.angle.valueChanged,
        ):
            self.watch(signal)

    def settings(self) -> tuple:
        return (
            api.parse_names(self.names.text),
            api.REFERENCES[self.reference.currentIndex][1],
            self.position.value / 100,
            self.angle.value,
        )

    def before_rows(self) -> None:
        self.position_label.setText(f"{self.position.value} %")

    def axis_flags(self) -> tuple[bool, bool]:
        return True, False

    def plan(self, layer: Any, master: str) -> list:
        return api.center_plan(layer, *self.settings())

    def render_row(self, old: tuple, new: Any, auto: bool) -> tuple:
        return (
            f"{old[0]}, {old[1]}",
            "auto, skipped" if auto else "empty" if new is None else new,
        ), not auto and new is not None and new != old[0]


class RoundAnchors(CoordinateDialog):
    TITLE, KEY = "Round Anchors to Grid", "anchors_round_to_grid"
    ACTION, VERB, WIDTH, HEIGHT = "Round", "Rounded", 540, 240
    HEADERS = ("Glyph · master", "Anchor", "Now", "Move", "New")

    def build_controls(self) -> None:
        form = self.form()
        self.step = QtGui.QSpinBox()
        self.step.setRange(1, 500)
        self.step.setValue(10)
        self.step.setSuffix(" units")
        self.step.setAlignment(QtCore.Qt.AlignRight)
        self.step.setStyleSheet(
            f"color: {QtGui.QColor(self.palette.color(QtGui.QPalette.WindowText)).name()};"
        )
        self.do_x, self.do_y = QtGui.QCheckBox("x"), QtGui.QCheckBox("y")
        self.do_x.setChecked(True)
        self.do_y.setChecked(True)
        self.names = QtGui.QLineEdit()
        self.names.setPlaceholderText("all anchors, or names: top, bottom")
        axes = QtGui.QHBoxLayout()
        axes.addWidget(self.do_x)
        axes.addWidget(self.do_y)
        axes.addStretch(1)
        form.addWidget(QtGui.QLabel("Grid step"), 0, 0)
        form.addWidget(self.step, 0, 1)
        form.addLayout(axes, 0, 2)
        form.addWidget(QtGui.QLabel("Anchors"), 1, 0)
        form.addWidget(self.names, 1, 1, 1, 2)
        form.addWidget(QtGui.QLabel("Masters"), 2, 0)
        form.addWidget(self.scope, 2, 1, 1, 2)
        form.setColumnStretch(1, 1)
        form.setColumnStretch(2, 1)
        for signal in (
            self.step.valueChanged,
            self.do_x.toggled,
            self.do_y.toggled,
            self.names.textChanged,
        ):
            self.watch(signal)

    def settings(self) -> tuple:
        return (
            self.step.value,
            self.do_x.isChecked(),
            self.do_y.isChecked(),
            set(api.parse_names(self.names.text)),
        )

    def axis_flags(self) -> tuple[bool, bool]:
        return self.do_x.isChecked(), self.do_y.isChecked()

    def plan(self, layer: Any, master: str) -> list:
        return api.round_plan(layer, *self.settings())

    def render_row(self, old: tuple, new: tuple, auto: bool) -> tuple:
        return (
            f"{old[0]}, {old[1]}",
            f"{new[0] - old[0]:+d}, {new[1] - old[1]:+d}",
            "auto, skipped" if auto else f"{new[0]}, {new[1]}",
        ), not auto

    def set_pending_status(self, count: int, rows: bool) -> None:
        self.status.setText(
            f"{count} anchor{'s' if count != 1 else ''} off the grid"
            if count
            else "All anchors already sit on the grid"
        )


class SnapAnchors(CoordinateDialog):
    TITLE, KEY = "Snap Anchors to Metrics", "anchors_snap_to_metrics"
    ACTION, VERB = "Snap", "Moved"
    HEADERS = ("Glyph · master", "Anchor", "x", "y", "New y")

    def build_controls(self) -> None:
        options = QtGui.QHBoxLayout()
        options.setSpacing(18)
        box = QtGui.QGroupBox("Snap to")
        radios = QtGui.QVBoxLayout(box)
        radios.setSpacing(6)
        self.group = QtGui.QButtonGroup(self)
        for index, (label, _) in enumerate(api.METRICS):
            radio = QtGui.QRadioButton(label)
            self.group.addButton(radio, index)
            radios.addWidget(radio)
        self.group.button(1).setChecked(True)
        options.addWidget(box)
        form = QtGui.QFormLayout()
        form.setVerticalSpacing(8)
        self.names = QtGui.QLineEdit("top")
        self.names.setPlaceholderText("anchor names, comma-separated")
        self.offset = QtGui.QSpinBox()
        self.offset.setRange(-1000, 1000)
        self.offset.setAlignment(QtCore.Qt.AlignRight)
        self.offset.setSuffix(" units")
        self.offset.setStyleSheet(
            f"color: {QtGui.QColor(self.palette.color(QtGui.QPalette.WindowText)).name()};"
        )
        self.values = QtGui.QLabel()
        self.values.setWordWrap(True)
        self.values.setStyleSheet(f"color: {muted(self)};")
        form.addRow("Anchors", self.names)
        form.addRow("Offset", self.offset)
        form.addRow("Masters", self.scope)
        form.addRow("", self.values)
        options.addLayout(form, 1)
        self.root.addLayout(options)
        for signal in (
            self.group.buttonClicked,
            self.names.textChanged,
            self.offset.valueChanged,
        ):
            self.watch(signal)

    def attribute(self) -> str | None:
        return api.METRICS[max(0, self.group.checkedId())][1]

    def choose_metric(self, label: str) -> None:
        self.group.button([name for name, _ in api.METRICS].index(label)).setChecked(
            True
        )
        self.refresh()

    def settings(self) -> tuple:
        return self.attribute(), self.offset.value

    def axis_flags(self) -> tuple[bool, bool]:
        return False, True

    def before_rows(self) -> None:
        heights = (
            {
                master: api.metric_value(self.package, master, self.attribute())
                for master in self.chosen_masters()
            }
            if self.package is not None
            else {}
        )
        label = api.METRICS[max(0, self.group.checkedId())][0]
        self.values.setText(
            f"{label}: "
            + ", ".join(f"{master} {value}" for master, value in heights.items())
        )

    def plan(self, layer: Any, master: str) -> list:
        return api.metric_plan(
            layer,
            api.parse_names(self.names.text),
            api.metric_value(self.package, master, self.attribute())
            + self.offset.value,
        )

    def render_row(self, old: tuple, new: Any, auto: bool) -> tuple:
        return (old[0], old[1], "auto, skipped" if auto else new), not auto and old[
            1
        ] != new
