# this_file: src/fontlabapp/contours/panel/ui.py
# SPDX-License-Identifier: Apache-2.0
"""The non-modal ``OutlinePanel`` base of the outline writer scripts (PythonQt).

Load it through ``fontlabapp.contours.panel.model.panel_type()``, inside FontLab
only: this module imports PythonQt at load time, like ``_component_panel``.
The plan and write kernel lives in ``fontlabapp.contours.writer``.

The panel calls ``scripting``, ``outline_writer`` and ``history`` through
their modules, never through names copied at import, so a replaced function
(for example a test double) takes effect at once.
"""

from collections.abc import Callable
from typing import Any

import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - the package __getattr__ is native
import fontlabapp.contours.writer as outline_writer  # noqa: PLR0402 - the package __getattr__ is native
import fontlabapp.core.scripting as scripting  # noqa: PLR0402 - the package __getattr__ is native
import fontlabapp.core.edit_guards as edit_guards

from fontlabapp import _native
from fontlabapp.contours.panel.model import (
    ERROR_COLOR,
    MAX_ROWS,
    ink,
    muted,
    readable_palette,
)

QtCore, QtGui = _native("PythonQt").QtCore, _native("PythonQt").QtGui


class OutlinePanel(QtGui.QDialog):
    """Non-modal panel: controls, live preview table, Reload, Close, Apply.

    Subclasses set TITLE, KEY, ACTION, DONE, UNIT, HEADERS and STRUCTURAL,
    and override build_controls(), planner() and editor(). The preview
    recomputes on every control change and shows exactly what Apply would
    write. Apply stays off while any row is blocked.
    """

    TITLE = ""
    KEY = ""
    ACTION = "Apply"
    DONE = "Changed"
    UNIT = "edit"
    HEADERS: tuple[str, ...] = ("Glyph · master", "Item", "Now", "After")
    STRUCTURAL = (
        False  # True: edits change node counts or order; offer the master check
    )
    SCOPE = 0  # scope at open: 0 current master, 1 all masters (structural: always 1)
    RELOAD = "Reload selection"
    WIDTH = 600

    def __init__(self, parent: Any = None) -> None:
        """Build every widget, then scan the font and the selection."""
        QtGui.QDialog.__init__(self, parent)
        readable_palette(self)
        self._connections: list[Any] = []  # filled by scripting.connect_guarded
        self.timers: list[Any] = []  # stopped when the panel closes
        self.slot_error = ""
        self.last_result: dict[str, Any] = {}
        self.glyphs: list[Any] = []
        self.facts = history.auto_facts(())
        self.form_row = 0
        self.rows = 0
        self.read_font()
        self.setWindowTitle(self.TITLE)
        self.setMinimumWidth(self.WIDTH)
        self.build()
        self.reload()

    # -- layout
    def build(self) -> None:
        """Create every widget before any font data is read."""
        root = QtGui.QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(12)
        heading = QtGui.QLabel(self.TITLE)
        font = heading.font
        font.setPointSizeF(font.pointSizeF() * 1.35)
        font.setBold(True)
        heading.setFont(font)
        root.addWidget(heading)
        self.subtitle = QtGui.QLabel()
        self.subtitle.setWordWrap(True)
        self.subtitle.setStyleSheet(f"color: {muted(self)};")
        root.addWidget(self.subtitle)
        self.form = QtGui.QGridLayout()
        self.form.setHorizontalSpacing(10)
        self.form.setVerticalSpacing(8)
        self.form.setColumnStretch(1, 1)
        root.addLayout(self.form)
        self.build_controls()
        self.scope = QtGui.QComboBox()
        self.scope.addItem("")
        self.scope.addItem("")
        self.scope.setCurrentIndex(1 if self.STRUCTURAL else self.SCOPE)
        self.relabel()
        self.add_row("Masters", self.scope)
        self.watch(self.scope.currentIndexChanged)
        self.compatible = QtGui.QCheckBox(outline_writer.COMPATIBLE_LABEL)
        self.compatible.setChecked(True)
        self.compatible.setVisible(self.STRUCTURAL)
        if self.STRUCTURAL:
            self.add_row("", self.compatible)
            self.watch(self.compatible.toggled)
        self.bases = QtGui.QCheckBox(outline_writer.BASES_LABEL)
        self.bases.setToolTip(
            "FontLab rebuilds the automatic composites of an edited base glyph. "
            "Check their anchors and locks after Apply. "
            "Reload selection clears this tick."
        )
        self.add_row("", self.bases)
        self.watch(self.bases.toggled)
        self.build_extra(root)
        self.table = QtGui.QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(list(self.HEADERS))
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QtGui.QAbstractItemView.NoSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QtGui.QHeaderView.Stretch)
        header.setSectionResizeMode(0, QtGui.QHeaderView.ResizeToContents)
        self.table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.table.setMinimumHeight(200)
        root.addWidget(self.table, 1)
        bar = QtGui.QHBoxLayout()
        self.status = QtGui.QLabel()
        self.status.setWordWrap(True)
        self.status.setStyleSheet(f"color: {muted(self)};")
        bar.addWidget(self.status, 1)
        self.reload_button = QtGui.QPushButton(self.RELOAD)
        self.close_button = QtGui.QPushButton("Close")
        self.apply_button = QtGui.QPushButton(self.ACTION)
        self.apply_button.setDefault(True)
        for button in (self.reload_button, self.close_button, self.apply_button):
            bar.addWidget(button)
        root.addLayout(bar)
        self.watch(self.reload_button.clicked, self.reload)
        self.watch(self.close_button.clicked, self.close)
        self.watch(self.apply_button.clicked, self.apply)

    def build_controls(self) -> None:
        """Subclass hook: add rows with add_row() and watch() their signals."""

    def build_extra(self, root: Any) -> None:
        """Subclass hook: add widgets between the form and the table."""

    def add_row(self, label: str, *widgets: Any) -> None:
        """Put a label and widgets on the next form row."""
        if label:
            self.form.addWidget(QtGui.QLabel(label), self.form_row, 0)
        for column, widget in enumerate(widgets, start=1):
            self.form.addWidget(widget, self.form_row, column)
        self.form_row += 1

    def watch(self, signal: Any, callback: Callable[..., Any] | None = None) -> None:
        """Connect through the guard: an exception in a PythonQt slot can exit FontLab."""
        action = callback or self.refresh
        scripting.connect_guarded(self, signal, lambda *args: action())

    def spin(
        self, low: float, high: float, value: float, suffix: str = "", decimals: int = 0
    ) -> Any:
        """Right-aligned, watched spin box with readable text.

        `decimals` 0 gives a QSpinBox with integers (PythonQt picks overloads
        by type), more gives a QDoubleSpinBox.
        """
        box = QtGui.QDoubleSpinBox() if decimals else QtGui.QSpinBox()
        if decimals:
            box.setDecimals(decimals)
            low, high, value = float(low), float(high), float(value)
        else:
            low, high, value = int(low), int(high), int(value)
        box.setStyleSheet(f"color: {ink().color().name()};")
        box.setRange(low, high)
        box.setValue(value)
        box.setSuffix(suffix)
        box.setAlignment(QtCore.Qt.AlignRight)
        box.setMaximumWidth(160)
        self.watch(box.valueChanged)
        return box

    def relabel(self) -> None:
        """Keep the scope combo in step with the font."""
        self.scope.setItemText(0, f"Current master ({self.current_master})")
        self.scope.setItemText(1, f"All masters ({len(self.masters)})")

    # -- data
    def planner(self) -> outline_writer.Planner:
        """Subclass hook: return the per-layer planner. Raise ValueError on bad input."""
        raise NotImplementedError

    def editor(self) -> outline_writer.Editor:
        """Subclass hook: return the write strategy."""
        raise NotImplementedError

    def chosen_masters(self) -> list[str]:
        """Masters in scope: current or all."""
        if self.scope.currentIndex == 0:
            return [self.current_master]
        return list(self.masters)

    def options(self) -> dict[str, Any]:
        """Keyword options of collect() from the shared check boxes."""
        return {
            "compatible": self.STRUCTURAL and self.compatible.isChecked(),
            "all_masters": list(self.masters),
            "allow_bases": self.bases.isChecked(),
        }

    def read_font(self) -> None:
        """Bind to the current font and its masters."""
        self.package = scripting.current_package()
        self.package_id = self.package.id if self.package is not None else None
        self.masters = list(self.package.masters) if self.package else []
        self.current_master = self.package.master if self.package else ""

    def reload(self) -> None:
        """Scan again. A failure shows in the status line and blocks Apply."""
        try:
            self.scan()
        except Exception as error:  # noqa: BLE001 - the first scan runs in the constructor
            self.slot_error = repr(error)
            self.glyphs, self.facts = [], history.auto_facts(())
            self.refresh()
            self.status.setText(f"Error: {error}")

    def scan(self) -> None:
        """Read font, selection and the auto-composite map again.

        The consent to edit bases of automatic composites belongs to the
        glyphs the user saw: a new scan clears it.
        """
        self.bases.setChecked(False)
        self.read_font()
        self.relabel()
        self.glyphs, self.facts = [], history.auto_facts(())
        if self.package is not None:
            found = (self.package.findName(n) for n in scripting.names_selected_names())
            self.glyphs = [glyph for glyph in found if glyph is not None]
            self.facts = history.scan_auto_facts(self.package)
        self.on_reload()
        self.refresh()

    def on_reload(self) -> None:
        """Subclass hook: refresh control contents that depend on the font."""

    def intro(self) -> str:
        """Subtitle text. Names the glyphs, or says what is missing."""
        if self.package is None:
            return "Open a font first."
        if not self.glyphs:
            return "Select glyphs in the Font window, then press Reload selection."
        count = len(self.glyphs)
        names = ", ".join(g.name for g in self.glyphs[:8]) + (" …" if count > 8 else "")
        return f"{count} glyph{'s' if count != 1 else ''}: {names}"

    def refresh(self) -> None:
        """Recompute the plan; fill the table; enable Apply only when it is safe."""
        self.subtitle.setText(self.intro())
        plan, problem = outline_writer.Plan(), ""
        if self.package is not None and self.glyphs:
            try:
                plan = outline_writer.collect(
                    self.glyphs,
                    self.chosen_masters(),
                    self.planner(),
                    self.facts,
                    **self.options(),
                )
            except (ValueError, RuntimeError) as error:
                problem = str(error)
        if plan.problems:
            problem = plan.problems[0]
        if plan.work and not problem:
            try:
                outline_writer.require_safe()
            except ValueError as error:
                problem = str(error)
        self.fill(plan)
        self.apply_button.setEnabled(bool(plan.work) and not problem)
        self.status.setText(problem or self.summary(plan))
        self.after_refresh()

    def after_refresh(self) -> None:
        """Subclass hook: update extra views after the table."""

    def summary(self, plan: outline_writer.Plan) -> str:
        """Status line when Apply is possible, or when nothing is to do."""
        notes = []
        if plan.refused:
            notes.append(f"{outline_writer.plural(len(plan.refused), 'glyph')} skipped")
        if plan.held:
            notes.append(
                f"{outline_writer.plural(len(plan.held), 'glyph')} held for compatibility"
            )
        tail = "".join(f" · {note}" for note in notes)
        if not plan.work:
            return f"Nothing to change{tail}" if self.glyphs else ""
        return f"{outline_writer.plural(plan.edits, self.UNIT)} on {outline_writer.plural(len(plan.work), 'layer')}{tail}"

    def fill(self, plan: outline_writer.Plan) -> None:
        """Show the first MAX_ROWS rows.

        Blocked rows red, changes in the accent colour, notes (skipped
        glyphs and layers, kept shapes, rows without a change) muted.
        """
        accent = QtGui.QColor(self.palette.color(QtGui.QPalette.Link))
        alarm = QtGui.QColor(ERROR_COLOR)
        quiet = QtGui.QColor(muted(self))
        rows = plan.rows[:MAX_ROWS]
        self.rows = len(rows)
        self.table.setRowCount(len(rows))
        for row, (label, change) in enumerate(rows):
            cells = self.cells(label, change)
            for column, text in enumerate(cells):
                item = QtGui.QTableWidgetItem(text)
                item.setForeground(ink())
                if column == len(cells) - 1:
                    if change.problem:
                        color = alarm
                    else:
                        color = accent if change.edit is not None else quiet
                    item.setForeground(QtGui.QBrush(color))
                self.table.setItem(row, column, item)

    def cells(self, label: str, change: outline_writer.Change) -> list[str]:
        """Row texts for 3 columns (glyph, item, result) or 4 (with current)."""
        last = change.problem or change.new
        if len(self.HEADERS) == 3:
            return [label, change.name, last]
        return [label, change.name, change.old, last]

    # -- action
    def live_glyphs(self) -> tuple[Any, list[Any]]:
        """Re-resolve the bound font and the scanned glyphs. ValueError when stale."""
        package = scripting.current_package(self.package_id)
        if package is None:
            raise ValueError("The font changed; press Reload selection.")
        if package.master != self.current_master:
            raise ValueError("Master changed; press Reload selection.")
        glyphs = [package.findName(glyph.name) for glyph in self.glyphs]
        if any(glyph is None or glyph.isNull for glyph in glyphs):
            raise ValueError("Glyphs changed; press Reload selection.")
        return package, glyphs

    def apply(self) -> None:
        """Plan again from live data, re-check safety, write once.

        A refusal or a failed write shows in the status line. A failure after
        history started says "use Edit > Undo".
        """
        try:
            package, glyphs = self.live_glyphs()
            outline_writer.require_safe()
            facts = history.scan_auto_facts(package)
            options = self.options()
            plan = outline_writer.collect(
                glyphs, self.chosen_masters(), self.planner(), facts, **options
            )
            if plan.problems:
                raise ValueError(plan.problems[0])
            if not plan.work:
                raise ValueError("Nothing to change.")
            result = outline_writer.apply_work(
                plan.work,
                self.TITLE,
                facts,
                self.editor(),
                allow_bases=options["allow_bases"],
            )
        except (ValueError, RuntimeError, TimeoutError) as error:
            self.slot_error = repr(error)
            self.refresh()
            self.status.setText(f"Error: {error}")
            return
        result["skipped"] = len(plan.refused) + len(plan.skipped)
        self.last_result = result
        self.refresh()
        note = f" · {result['skipped']} skipped" if result["skipped"] else ""
        queued = result.get("pending_note", "")
        note += f" · {queued}" if queued else ""
        self.status.setText(
            f"{self.DONE} {outline_writer.plural(result['edits'], self.UNIT)} "
            f"on {outline_writer.plural(result['layers'], 'layer')}{note}"
        )

    def closeEvent(self, event: Any) -> None:
        """Disconnect every slot, stop timers, unregister and delete the panel."""
        scripting.close_script_dialog(self, event, self.KEY, timers=self.timers)
