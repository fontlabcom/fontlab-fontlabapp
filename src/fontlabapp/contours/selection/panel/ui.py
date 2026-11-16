# this_file: src/fontlabapp/contours/selection/panel/ui.py
# SPDX-License-Identifier: Apache-2.0
"""The non-modal ``SelectionPanel`` and ``CopiesPanel`` bases of the Contours scripts (PythonQt).

Load them through ``fontlabapp.contours.selection.panel.model.panel_type()`` and
``fontlabapp.glyphs.copies.panel_type()``, inside FontLab only: this module
imports PythonQt at load time, like ``_outline_panel``.

The panels call ``scripting``, ``history``, ``glyph_copies`` and
``glyph_creation`` through their modules, never through names copied at
import, so a replaced function (for example a test double) takes effect at
once.
"""

from collections.abc import Callable, Sequence
from typing import Any

import fontlabapp.glyphs.copies as glyph_copies  # noqa: PLR0402 - the package __getattr__ is native
import fontlabapp.glyphs.creation as glyph_creation  # noqa: PLR0402 - the package __getattr__ is native
import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - the package __getattr__ is native
import fontlabapp.core.scripting as scripting  # noqa: PLR0402 - the package __getattr__ is native
import fontlabapp.core.edit_guards as edit_guards

from fontlabapp import _native
from fontlabapp.masters.layers.writer import plural
from fontlabapp.contours.selection.panel.model import BASES_TEXT, MAX_NAMES, MAX_ROWS

QtCore, QtGui = _native("PythonQt").QtCore, _native("PythonQt").QtGui
#: Refusals that the panel shows in the status line instead of raising.
REFUSALS = (ValueError, RuntimeError, TimeoutError)


class SelectionPanel(QtGui.QDialog):
    """Non-modal panel: controls, scope, consent, preview table, Use selection, Close, action.

    Subclasses set TITLE, KEY, ACTION and HEADERS and fill in the hooks
    build_controls(), plan_rows(), cells(), pending(), write() and
    result_text(). ``facts`` stores the auto-layer snapshot from construction,
    reselect() or scan() (explicit Refresh). Control changes reuse it.
    SCOPE False hides the master scope (every master is
    planned); CONSENT "" hides the consent tick. ALIGN right-aligns the
    value columns of ready rows. NOUN names the selection in messages.
    """

    TITLE = ""
    KEY = ""
    ACTION = "Apply"
    HEADERS: tuple[str, ...] = ("Glyph · master", "Value")
    NOUN = "glyphs"
    SCOPE = True
    CONSENT = BASES_TEXT
    ALIGN = True
    WIDTH = 560
    TABLE_HEIGHT = 240

    def __init__(self, parent: Any = None) -> None:
        """Build every widget, bind the current font and selection, then plan."""
        QtGui.QDialog.__init__(self, parent)
        self._connections: list[Any] = []  # filled by scripting.connect_guarded
        self.facts: history.AutoFacts = history.auto_facts(())
        self.rows: list[Any] = []
        self.names: list[str] = []
        self.font_masters: list[str] = []
        self.package_id: int | None = None
        self.last_result: dict[str, Any] = {}
        self.form_row = 0
        self.setWindowTitle(self.TITLE)
        self.setMinimumWidth(self.WIDTH)
        self.build()
        try:
            package = scripting.current_package()
            if package is not None:
                self.package_id = package.id
                self.names = scripting.names_selected_names()
                self.facts = history.scan_auto_facts(package)
        except REFUSALS as error:
            self.status.setText(str(error))
        self.refresh()

    # -- layout
    def build(self) -> None:
        """Create every widget before any font data is read."""
        root = QtGui.QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(12)
        heading = QtGui.QLabel(self.TITLE)
        face = heading.font
        face.setPointSizeF(face.pointSizeF() * 1.35)
        face.setBold(True)
        heading.setFont(face)
        root.addWidget(heading)
        self.subtitle = QtGui.QLabel("")
        self.subtitle.setWordWrap(True)
        root.addWidget(self.subtitle)
        self.grid = QtGui.QGridLayout()
        self.grid.setHorizontalSpacing(10)
        self.build_controls()
        self.scope: Any = None
        if self.SCOPE:
            self.scope = QtGui.QComboBox()
            self.scope.addItem("Current master")
            self.scope.addItem("All masters")
            self.add_row("Masters", self.scope)
            self.watch(self.scope.currentIndexChanged)
        self.consent: Any = None
        if self.CONSENT:
            self.consent = QtGui.QCheckBox(self.CONSENT)
            self.add_row("", self.consent)
            self.watch(self.consent.toggled)
        root.addLayout(self.grid)
        self.table = QtGui.QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(list(self.HEADERS))
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QtGui.QHeaderView.Stretch)
        self.table.setMinimumHeight(self.TABLE_HEIGHT)
        root.addWidget(self.table, 1)
        footer = QtGui.QHBoxLayout()
        self.status = QtGui.QLabel("")
        self.status.setWordWrap(True)
        footer.addWidget(self.status, 1)
        self.selection_button = QtGui.QPushButton("Use selection")
        self.close_button = QtGui.QPushButton("Close")
        self.apply_button = QtGui.QPushButton(self.ACTION)
        self.apply_button.setDefault(True)
        for button in (self.selection_button, self.close_button, self.apply_button):
            footer.addWidget(button)
        root.addLayout(footer)
        self.watch(self.selection_button.clicked, self.reselect)
        self.watch(self.apply_button.clicked, self.apply)
        self.watch(self.close_button.clicked, self.close)

    def build_controls(self) -> None:
        """Subclass hook: create the controls, add_row() them and watch() their signals."""

    def add_row(self, label: str, *widgets: Any) -> None:
        """Put a label and widgets on the next grid row."""
        if label:
            self.grid.addWidget(QtGui.QLabel(label), self.form_row, 0)
        for column, widget in enumerate(widgets, start=1):
            self.grid.addWidget(widget, self.form_row, column)
        self.form_row += 1

    def watch(self, signal: Any, callback: Callable[..., Any] | None = None) -> None:
        """Connect through the guard: an exception in a PythonQt slot can exit FontLab."""
        action = callback or self.refresh
        scripting.connect_guarded(self, signal, lambda *args: action())

    # -- data
    def font_package(self) -> Any:
        """Return the bound font. Refuse a closed or switched font."""
        if self.package_id is None:
            raise ValueError(
                f"Open a font and select {self.NOUN}. Then run this script again."
            )
        package = scripting.current_package()
        if package is None or package.id != self.package_id:
            raise ValueError("The font changed. Run this script again.")
        return package

    def consented(self) -> bool:
        """True when the consent tick exists and the user ticked it."""
        return self.consent is not None and bool(self.consent.isChecked())

    def chosen_masters(self, package: Any) -> list[str]:
        """Masters in scope: the current master, or every master (also without a scope)."""
        if self.scope is not None and self.scope.currentIndex == 0:
            return [package.master]
        return list(package.masters)

    def plan(self) -> list[Any]:
        """Plan from the live font. A missing font or selection raises ValueError."""
        package = self.font_package()
        if not self.names:
            raise ValueError(
                f"Select {self.NOUN} in the Font window. Then press Use selection."
            )
        self.font_masters = list(package.masters)
        return self.plan_rows(package, self.chosen_masters(package))

    def plan_rows(self, package: Any, masters: list[str]) -> list[Any]:
        """Subclass hook: return the preview rows for ``masters``. Change nothing."""
        raise NotImplementedError

    def is_ready(self, row: Any) -> bool:
        """True when ``row`` will be written: it has no note."""
        return not row.note

    def cells(self, row: Any) -> list[str]:
        """Subclass hook: the table texts of ``row``, one per header."""
        raise NotImplementedError

    def pending(self, todo: Sequence[Any]) -> str:
        """Subclass hook: the status text for the ready rows before the action."""
        return f"{plural(len(todo), 'row')} ready"

    def intro(self) -> str:
        """Subtitle text: the number of selected glyphs and their first names."""
        shown = ", ".join(self.names[:MAX_NAMES]) + (
            " …" if len(self.names) > MAX_NAMES else ""
        )
        return f"{plural(len(self.names), 'glyph')}: {shown}"

    def refresh(self) -> None:
        """Recompute the preview. A refusal disables the action and shows its reason."""
        try:
            self.rows = self.plan()
        except REFUSALS as error:
            self.rows = []
            self.table.setRowCount(0)
            self.subtitle.setText(str(error))
            self.apply_button.setEnabled(False)
            return
        self.subtitle.setText(self.intro())
        visible = self.rows[:MAX_ROWS]
        self.table.setRowCount(len(visible))
        for number, row in enumerate(visible):
            for column, text in enumerate(self.cells(row)):
                item = QtGui.QTableWidgetItem(text)
                if self.ALIGN and column and self.is_ready(row):
                    item.setTextAlignment(
                        int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                    )
                self.table.setItem(number, column, item)
        todo = [row for row in self.rows if self.is_ready(row)]
        self.apply_button.setEnabled(bool(todo))
        more = (
            f" (table shows the first {MAX_ROWS})" if len(self.rows) > MAX_ROWS else ""
        )
        self.status.setText(self.pending(todo) + more)

    # -- actions
    def scan(self) -> None:
        """Read fresh auto-layer facts, then refresh the preview.

        Connect an explicit Refresh button to this method. Control signals
        use refresh() to reuse the public facts snapshot and avoid a font scan.
        """
        try:
            self.facts = history.scan_auto_facts(self.font_package())
        except REFUSALS as error:
            self.status.setText(str(error))
            return
        self.refresh()

    def reselect(self) -> None:
        """Take the Font window selection again; clear the consent; plan again.

        A refusal (closed or switched font, unreadable selection) shows in
        the status line, as in apply().
        """
        try:
            package = self.font_package()
            self.names = scripting.names_selected_names()
            self.facts = history.scan_auto_facts(package)
        except REFUSALS as error:
            self.status.setText(str(error))
            return
        if self.consent is not None:
            self.consent.setChecked(False)
        self.on_reselect()
        self.refresh()

    def on_reselect(self) -> None:
        """Subclass hook: forget results that belong to the old selection."""

    def write(self, package: Any, rows: list[Any]) -> dict[str, Any]:
        """Subclass hook: write the ready rows (one Undo step) and return the result."""
        raise NotImplementedError

    def result_text(self, result: dict[str, Any]) -> str:
        """Subclass hook: the status text after the action."""
        return "Done"

    def on_result(self, result: dict[str, Any]) -> None:
        """Subclass hook: keep values of the result before the preview is planned again."""

    def apply(self) -> None:
        """Plan again from the live font, then write once. A refusal shows in the status line."""
        try:
            package = self.font_package()
            self.facts = history.scan_auto_facts(package)
            rows = self.plan()
            result = self.write(package, rows)
        except REFUSALS as error:
            self.refresh()
            self.status.setText(str(error))
            return
        self.last_result = result
        self.on_result(result)
        self.refresh()
        text = self.result_text(result)
        if result.get("mismatches"):
            text += " · did not read back as planned: " + "; ".join(
                result["mismatches"][:5]
            )
        note = result.get("pending_note", "")
        self.status.setText(f"{text} · {note}" if note else text)

    def closeEvent(self, event: Any) -> None:
        """Disconnect owned signals, then delete the panel."""
        scripting.close_script_dialog(self, event, self.KEY)


class CopiesPanel(SelectionPanel):
    """Panel of the scripts that create glyph copies: source, new glyph, action.

    Subclasses set TITLE, KEY and NOUN and fill in build_controls(),
    survey(package, facts, allow_rebuild) and jobs(rows). Every master gets
    a copy, so there is no master scope. The consent tick lets a new glyph
    through that can make FontLab rebuild automatic glyphs
    (``glyph_creation.REBUILD_LABEL``); Use selection clears it.
    """

    ACTION = "Create"
    HEADERS = ("Source", "New glyph", "Action")
    SCOPE = False
    CONSENT = glyph_creation.REBUILD_LABEL
    ALIGN = False
    WIDTH = 520
    TABLE_HEIGHT = 220

    def survey(
        self, package: Any, facts: history.AutoFacts, allow_rebuild: bool
    ) -> list[Any]:
        """Subclass hook: plan one ``glyph_copies.Row`` per selected name."""
        raise NotImplementedError

    def jobs(self, rows: list[Any]) -> list[glyph_copies.Job]:
        """Subclass hook: return the jobs (copied contours and widths) of the ready rows."""
        raise NotImplementedError

    def plan_rows(self, package: Any, masters: list[str]) -> list[Any]:
        """Plan with the public facts snapshot and the consent tick."""
        return self.survey(package, self.facts, self.consented())

    def cells(self, row: Any) -> list[str]:
        """Source, new glyph, and the note or "create on N masters" (with the rebuild note)."""
        action = row.note or f"create on {len(self.font_masters)} masters"
        if row.rebuild and not row.note:
            action += " · " + glyph_creation.rebuild_note(row.rebuild)
        return [row.source, row.target, action]

    def pending(self, todo: Sequence[Any]) -> str:
        """Status before Create: N glyphs to create."""
        return f"{plural(len(todo), 'glyph')} to create"

    def write(self, package: Any, rows: list[Any]) -> dict[str, Any]:
        """Create glyphs with the facts that apply() scanned just before planning."""
        return glyph_copies.create(
            package, self.jobs(rows), self.TITLE, self.facts, allow_rebuild=self.consented()
        )

    def result_text(self, result: dict[str, Any]) -> str:
        """Status after Create: Created N glyphs (M master layers), or Nothing to create."""
        if not result["glyphs"]:
            return "Nothing to create"
        return f"Created {plural(result['glyphs'], 'glyph')} ({plural(result['layers'], 'master layer')})"
