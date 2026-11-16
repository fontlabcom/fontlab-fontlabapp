# this_file: src/fontlabapp/anchors/panel/ui.py
# SPDX-License-Identifier: Apache-2.0
"""The non-modal ``AnchorPanel`` base of the anchor writer scripts (PythonQt).

Load it through ``fontlabapp.anchors.panel.model.panel_type()``, inside FontLab
only: this module imports PythonQt at load time, like ``_metrics_panel``.
The plan and write kernel lives in ``fontlabapp.anchors.writer``.

The panel calls ``scripting``, ``anchor_writer``, ``history`` and
``edit_guards`` through their modules, never through names copied at import,
so a replaced function (for example a test double) takes effect at once.
"""

from collections.abc import Callable
from typing import Any

import fontlabapp.anchors.writer as anchor_writer  # noqa: PLR0402 - the package __getattr__ is native
import fontlabapp.core.edit_guards as edit_guards  # noqa: PLR0402 - the package __getattr__ is native
import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - the package __getattr__ is native
import fontlabapp.core.scripting as scripting  # noqa: PLR0402 - the package __getattr__ is native
from fontlabapp import _native
from fontlabapp.anchors.panel.model import (
    ERROR_COLOR,
    MAX_ROWS,
    ink,
    muted,
    readable_palette,
)

QtCore, QtGui = _native("PythonQt").QtCore, _native("PythonQt").QtGui


class AnchorPanel(QtGui.QDialog):
    """Non-modal panel: script controls, live preview table, Reload, Close, Apply.

    What: a subclass sets ``TITLE``, ``KEY``, ``ACTION`` (the Apply button
    text) and ``HEADERS`` (3 or 4 columns), and fills in ``build_controls``
    and ``planner``. Optional hooks: ``chosen_masters``, ``glyph_names`` and
    ``on_reload``. Helpers for subclasses: ``watch``, ``spin``, ``scope_box``.

    How: every control change recomputes the plan from the live font and
    shows exactly what Apply would write. Apply stays off while any row is
    blocked or ``require_safe`` refuses. Apply binds to the font, master and
    glyphs of the last scan, plans again, scans the auto-layer facts again and
    writes once through ``anchor_writer.apply_work``.

    Why: the preview can never be stale at Apply, and an exception in a slot
    stays in the status line instead of reaching FontLab. Show it with
    ``scripting.show_script_dialog(Subclass, Subclass.KEY)``.
    """

    TITLE = ""
    KEY = ""
    ACTION = "Apply"
    HEADERS: tuple[str, ...] = ("Glyph · master", "Anchor", "Current", "New")
    WIDTH = 580

    def __init__(self, parent: Any = None) -> None:
        """Build every widget, then scan the font. A scan failure shows in the status."""
        QtGui.QDialog.__init__(self, parent)
        readable_palette(self)
        self._connections: list[Any] = []  # filled by scripting.connect_guarded
        self.timers: list[Any] = []  # stopped when the panel closes
        self.slot_error = ""
        self.last_result: dict[str, Any] = {}
        self.glyphs: list[Any] = []
        self.facts = history.auto_facts(())
        self.scopes: list[Any] = []
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
        self.table.setMinimumHeight(220)
        root.addWidget(self.table, 1)
        bar = QtGui.QHBoxLayout()
        self.status = QtGui.QLabel()
        self.status.setStyleSheet(f"color: {muted(self)};")
        bar.addWidget(self.status, 1)
        self.reload_button = QtGui.QPushButton("Reload selection")
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
        """Subclass hook: add widgets to ``self.form`` and ``self.watch()`` their signals."""

    def watch(self, signal: Any, callback: Callable[..., Any] | None = None) -> None:
        """Connect ``signal`` through the guard; the default callback is ``refresh``.

        An exception in a PythonQt slot can exit FontLab, so the guard shows
        it in the status line instead. The slot drops the signal arguments.
        """
        action = callback or self.refresh
        scripting.connect_guarded(self, signal, lambda *args: action())

    def spin(self, low: int, high: int, value: int, suffix: str = "") -> Any:
        """Return a right-aligned integer ``QSpinBox`` with readable text."""
        box = QtGui.QSpinBox()
        box.setStyleSheet(f"color: {ink().color().name()};")
        box.setRange(low, high)
        box.setValue(value)
        box.setSuffix(suffix)
        box.setAlignment(QtCore.Qt.AlignRight)
        return box

    def scope_box(self) -> Any:
        """Return a combo box: 0 is the current master, 1 is all masters."""
        box = QtGui.QComboBox()
        box.addItem("")
        box.addItem("")
        self.scopes.append(box)
        self.relabel()
        return box

    def relabel(self) -> None:
        """Keep the scope combo texts in step with the font and its masters."""
        for box in self.scopes:
            box.setItemText(0, f"Current master ({self.current_master})")
            box.setItemText(1, f"All masters ({len(self.masters)})")

    # -- data
    def planner(self) -> anchor_writer.Planner:
        """Subclass hook: return the per-layer planner. Raise ``ValueError`` on bad input."""
        raise NotImplementedError

    def chosen_masters(self) -> list[str]:
        """Return the masters to plan. Default: all masters of the font."""
        return list(self.masters)

    def read_font(self) -> None:
        """Bind to the current font, its masters and its current master."""
        self.package = scripting.current_package()
        self.package_id = self.package.id if self.package is not None else None
        self.masters = list(self.package.masters) if self.package else []
        self.current_master = self.package.master if self.package else ""

    def reload(self) -> None:
        """Scan again. A failure shows "Error: ..." in the status and blocks Apply."""
        try:
            self.scan()
        except Exception as error:  # noqa: BLE001 - the first scan runs in the constructor
            self.slot_error = repr(error)
            self.glyphs, self.facts = [], history.auto_facts(())
            self.refresh()
            self.status.setText(f"Error: {error}")

    def scan(self) -> None:
        """Read the font, the selection and the auto-composite facts again."""
        self.read_font()
        self.relabel()
        self.glyphs, self.facts = [], history.auto_facts(())
        if self.package is not None:
            found = (self.package.findName(n) for n in self.glyph_names())
            self.glyphs = [glyph for glyph in found if glyph is not None]
            self.facts = history.scan_auto_facts(self.package)
        self.on_reload()
        self.refresh()

    def glyph_names(self) -> list[str]:
        """Return the glyphs to work on: the Font window selection, or the current glyph."""
        return scripting.names_selected_names()

    def on_reload(self) -> None:
        """Subclass hook: refresh control contents that depend on the font."""

    def intro(self) -> str:
        """Return the subtitle: the glyph names, or what is missing."""
        if self.package is None:
            return "Open a font first."
        if not self.glyphs:
            return "Select glyphs in the Font window, then press Reload selection."
        count = len(self.glyphs)
        names = ", ".join(g.name for g in self.glyphs[:8]) + (" …" if count > 8 else "")
        return f"{count} glyph{'s' if count != 1 else ''}: {names}"

    def refresh(self) -> None:
        """Plan again, fill the table and enable Apply only when the plan is safe."""
        self.subtitle.setText(self.intro())
        plan, problem = anchor_writer.Plan(), ""
        if self.package is not None and self.glyphs:
            try:
                plan = anchor_writer.collect(
                    self.glyphs, self.chosen_masters(), self.planner()
                )
            except ValueError as error:
                problem = str(error)
        if plan.problems:
            problem = plan.problems[0]
        if plan.work:
            plan.rows[:0] = anchor_writer.blocked_rows(plan.work, self.facts)
            if not problem:
                try:
                    anchor_writer.require_safe(plan.work, self.facts)
                except ValueError as error:
                    problem = str(error)
        self.fill(plan)
        self.apply_button.setEnabled(bool(plan.work) and not problem)
        self.status.setText(
            problem
            or f"{anchor_writer.plural(plan.anchors, 'anchor change')} on "
            f"{anchor_writer.plural(len(plan.work), 'layer')}"
        )

    def fill(self, plan: anchor_writer.Plan) -> None:
        """Show the first ``MAX_ROWS`` rows of the plan.

        The last cell is ``ERROR_COLOR`` for a blocked row, the link colour
        for a change, and the muted colour for a note (a skipped auto layer).
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

    def cells(self, label: str, change: anchor_writer.Change) -> list[str]:
        """Return the row texts: 3 columns (glyph, anchor, result) or 4 (with current)."""
        last = change.problem or change.new
        if len(self.HEADERS) == 3:
            return [label, change.name, last]
        return [label, change.name, change.old, last]

    # -- action
    def apply(self) -> None:
        """Plan again from live data, check safety again and write once.

        Refuse ("Reload selection") when the font, the current master or a
        glyph changed since the scan. The status then says what changed.
        """
        try:
            package = scripting.current_package(self.package_id)
            if package is None:
                raise ValueError("The font changed; press Reload selection.")
            if package.master != self.current_master:
                raise ValueError("Master changed; Reload selection.")
            glyphs = [package.findName(glyph.name) for glyph in self.glyphs]
            if any(glyph is None or glyph.isNull for glyph in glyphs):
                raise ValueError("Glyphs changed; Reload selection.")

            plan = anchor_writer.collect(glyphs, self.chosen_masters(), self.planner())
            if plan.problems:
                raise ValueError(plan.problems[0])
            facts = history.scan_auto_facts(package)
            anchor_writer.require_safe(plan.work, facts)
            self.last_result = anchor_writer.apply_work(plan.work, self.TITLE, facts)

            self.last_result["skipped"] = plan.skipped
        finally:
            self.refresh()
        result = self.last_result
        skipped = len(result["skipped"])
        plural = anchor_writer.plural
        note = f" · {plural(skipped, 'auto layer')} skipped" if skipped else ""
        queued = result.get("pending_note", "")
        note += f" · {queued}" if queued else ""
        self.status.setText(
            f"Changed {plural(result['anchors'], 'anchor')} "
            f"on {plural(result['layers'], 'layer')}{note}"
        )

    def closeEvent(self, event: Any) -> None:
        """Stop the timers, disconnect every signal, unregister and delete the panel."""
        scripting.close_script_dialog(self, event, self.KEY, timers=self.timers)
