# this_file: src/fontlabapp/studios/_kerning_ui.py
# SPDX-License-Identifier: Apache-2.0
"""Qt pieces shared by the Kerning Browser and Kerning Batch tabs.

What: small widget helpers (button, check box, label, combo, spin box, form
row), ``Panel`` (a tab bound to a ``studios._kerning.Tool``: subtitle, sortable
``GlyphTable`` tables, status-line errors), ``CheckTable`` (a table whose
first column is ticked, for Exceptions and Copy masters) and ``PlanPanel``,
the dry-run-then-Apply tab of Kerning Batch: Refresh takes one kerning
snapshot and builds the plan, the table and count show exactly that plan, and
Apply writes exactly that plan with ``expected=`` the snapshot, so any outside
edit in between is refused as stale.
Used by the tab modules of ``fontlabapp.studios.kerning_browser`` and
``fontlabapp.studios.kerning_batch``.
"""

from collections.abc import Callable
from typing import Any

from PythonQt import QtCore, QtGui

import fontlabapp.fontui as fontui

from ._kerning import ERRORS, Tool


def get(value: Any) -> Any:
    """PythonQt exposes some getters as properties, PySide6 as methods."""
    return value() if callable(value) else value


def button(owner: Any, layout: Any, text: str, slot: Callable[[], Any]) -> Any:
    widget = QtGui.QPushButton(text, owner)
    widget.setAccessibleName(text)
    widget.clicked.connect(lambda *args: slot())
    layout.addWidget(widget)
    return widget


def check(owner: Any, layout: Any, text: str, checked: bool, slot: Callable[[], Any] | None = None) -> Any:
    box = QtGui.QCheckBox(text, owner)
    box.setAccessibleName(text)
    box.setChecked(checked)
    if slot is not None:
        box.toggled.connect(lambda *args: slot())
    layout.addWidget(box)
    return box


def label(owner: Any, layout: Any, text: str = "") -> Any:
    widget = QtGui.QLabel(text, owner)
    widget.setWordWrap(True)
    layout.addWidget(widget)
    return widget


def row(owner: Any, layout: Any, text: str, widget: Any) -> Any:
    """``text`` then ``widget`` on one line (the originals' form rows)."""
    line = QtGui.QHBoxLayout()
    layout.addLayout(line)
    label(owner, line, text)
    line.addWidget(widget, 1)
    widget.setAccessibleName(text)
    return widget


def combo(owner: Any, items: list[str], slot: Callable[[], Any] | None = None) -> Any:
    box = QtGui.QComboBox(owner)
    for item in items:
        box.addItem(item)
    if slot is not None:
        box.currentIndexChanged.connect(lambda *args: slot())
    return box


def spin(owner: Any, low: float, high: float, value: float, *, suffix: str = "", prefix: str = "",
         decimals: int = 0, slot: Callable[[], Any] | None = None) -> Any:
    box = QtGui.QDoubleSpinBox(owner) if decimals else QtGui.QSpinBox(owner)
    if decimals:
        box.setDecimals(decimals)
    box.setRange(low, high)
    box.setValue(value)
    box.setSuffix(suffix)
    box.setPrefix(prefix)
    if slot is not None:
        box.valueChanged.connect(lambda *args: slot())
    return box


def line_edit(owner: Any, text: str = "", placeholder: str = "", slot: Callable[[], Any] | None = None) -> Any:
    edit = QtGui.QLineEdit(text, owner)
    edit.setPlaceholderText(placeholder)
    edit.setAccessibleName(placeholder or text)
    if slot is not None:
        edit.textChanged.connect(lambda *args: slot())
    return edit


def clipboard(text: str) -> None:
    QtGui.QApplication.clipboard().setText(text)


class Panel:
    """A tab widget bound to the tool; ``refresh`` runs after every reload."""

    def __init__(self, tool: Tool) -> None:
        self.tool = tool
        self.widget = QtGui.QWidget()
        self.layout = QtGui.QVBoxLayout(self.widget)
        self.subtitle = label(self.widget, self.layout)
        tool.views.append(self.reload_view)

    def table(self, columns: list[str], slot: Callable[..., Any] | None = None, stretch: int = 1) -> Any:
        table = fontui.glyph_table(columns, self.widget)
        if slot is not None:
            table.row_selected.connect(slot)
        self.layout.addWidget(self.tool.shell.embed(table), stretch)
        return table

    def scope_box(self, layout: Any, *, plain: bool = False, title: str = "Masters") -> Any:
        """The originals' master scope combo: current master first (the default), then all."""
        box = combo(self.widget, [], self.contain(self.refresh))
        self.scope_plain = plain
        row(self.widget, layout, title, box)
        return box

    def fill_scope(self, box: Any) -> None:
        tool = self.tool
        index = max(get(box.currentIndex), 0)
        box.blockSignals(True)
        box.clear()
        if self.scope_plain:
            box.addItem("Current master")
            box.addItem("All masters")
        else:
            box.addItem(f"Current master ({tool.current})")
            box.addItem(f"All masters ({len(tool.masters)})")
        box.setCurrentIndex(index)
        box.blockSignals(False)

    def refresh(self) -> None:  # pragma: no cover - overridden
        pass

    def clear(self) -> None:
        """Drop what the tab shows after a failed read, so nothing stale can be exported or written."""

    def failed(self, error: BaseException) -> None:
        """Show a read failure in the subtitle and status line instead of raising out of a Qt slot."""
        text = f"{self.tool.app}: {error}"
        self.clear()
        self.subtitle.setText(text)
        self.tool.say(text)

    def reload_view(self) -> None:
        """What ``Tool.reload`` runs: ``refresh`` with read failures contained (see ``failed``)."""
        self.contain(self.refresh)()

    def contain(self, slot: Callable[..., Any]) -> Callable[..., Any]:
        """Wrap a refresh or widget slot: ``ERRORS`` go to ``failed``; other tabs keep refreshing."""

        def contained(*args: Any) -> Any:
            try:
                return slot(*args)
            except ERRORS as error:
                self.failed(error)
                return None

        return contained

    def run(self, action: Callable[[], Any]) -> Any:
        """Run a button action; a refusal goes to the status line."""
        try:
            self.tool.shell.package()
            return action()
        except ERRORS as error:
            self.tool.say(f"{self.tool.app}: {error}")
            return None


def SortItem(text: str) -> Any:  # noqa: N802 - item factory shared with master tables
    """Keep displayed numeric text while sorting by value; load Qt only on construction."""
    class NumericItem(QtGui.QTableWidgetItem):
        def __lt__(self, other: Any) -> bool:
            try:
                return float(self.text()) < float(other.text())
            except ValueError:
                return self.text() < other.text()

    return NumericItem(text)


class CheckTable:
    """A plain table whose first column is a tick box; ``ticked()`` lists ticked row indexes."""

    def __init__(self, owner: Any, layout: Any, columns: list[str], slot: Callable[[], Any] | None = None) -> None:
        self.view = QtGui.QTableWidget(0, len(columns), owner)
        self.view.setHorizontalHeaderLabels(columns)
        self.view.setAccessibleName(columns[0])
        self.view.horizontalHeader().setStretchLastSection(True)
        self.view.horizontalHeader().setSectionResizeMode(QtGui.QHeaderView.Interactive)
        self.view.horizontalHeader().setSortIndicator(-1, QtCore.Qt.AscendingOrder)
        self.view.setSortingEnabled(True)
        self.view.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.view, 1)
        self.filling = False
        self.slot = slot
        self.view.itemChanged.connect(lambda *args: None if self.filling or slot is None else slot())

    def set_rows(self, rows: list[tuple], checked: list[bool] | None = None) -> None:
        self.filling = True
        self.view.setSortingEnabled(False)
        self.view.setRowCount(0)
        for number, values in enumerate(rows):
            self.view.insertRow(number)
            for column, value in enumerate(values):
                item = SortItem(str(value))
                if column == 0:
                    item.setData(QtCore.Qt.UserRole, number)
                    item.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
                    on = bool(checked and checked[number])
                    item.setCheckState(QtCore.Qt.Checked if on else QtCore.Qt.Unchecked)
                self.view.setItem(number, column, item)
        self.view.setSortingEnabled(True)
        self.filling = False

    def ticked(self) -> list[int]:
        return [self.view.item(n, 0).data(QtCore.Qt.UserRole) for n in range(get(self.view.rowCount))
                if self.view.item(n, 0).checkState() == QtCore.Qt.Checked]

    def set_ticked(self, numbers: set[int]) -> None:
        self.filling = True
        for n in range(get(self.view.rowCount)):
            self.view.item(n, 0).setCheckState(QtCore.Qt.Checked if self.view.item(n, 0).data(QtCore.Qt.UserRole) in numbers else QtCore.Qt.Unchecked)
        self.filling = False
        if self.slot is not None:
            self.slot()

    def text(self, number: int, column: int) -> str:
        return next(self.view.item(row, column).text() for row in range(get(self.view.rowCount))
                    if self.view.item(row, 0).data(QtCore.Qt.UserRole) == number)


class PlanPanel(Panel):
    """Kerning Batch dry run: Refresh builds one plan from one snapshot; Apply writes exactly that plan.

    Subclasses define ``build_controls(form)``, ``plan(snapshot) -> (edits, rows, status)``
    and ``result(edits) -> str``; ``ACTION`` names the Apply button and the Undo label.
    """

    ACTION = "Apply"
    #: The Undo label's action when it differs from the button text (lower case, as the other tabs).
    UNDO = ""
    COLUMNS: tuple[str, ...] = ()
    TYPED = False

    def __init__(self, tool: Tool) -> None:
        super().__init__(tool)
        form = QtGui.QVBoxLayout()
        self.layout.addLayout(form)
        self.build_controls(form)
        self.grid = self.table(list(self.COLUMNS), self.row_chosen)
        self.count = label(self.widget, self.layout)
        buttons = QtGui.QHBoxLayout()
        self.layout.addLayout(buttons)
        button(self.widget, buttons, "Refresh", tool.reload)
        self.apply_button = button(self.widget, buttons, self.ACTION, self.apply)
        self.snapshot: Any = None
        self.edits: dict = {}
        self.rows: list[tuple] = []

    def build_controls(self, form: Any) -> None:  # pragma: no cover - overridden
        pass

    def plan(self, snapshot: Any) -> tuple[dict, list[tuple], str]:  # pragma: no cover - overridden
        raise NotImplementedError

    def result(self, edits: dict) -> str:  # pragma: no cover - overridden
        raise NotImplementedError

    def changed_masters(self) -> str:
        """``"Regular, Bold"``: the masters the plan changes."""
        return ", ".join(m for m, changes in self.edits.items() if changes)

    def subject(self) -> str:
        """``"kerning on Regular, Bold"``: the masters the plan changes."""
        return "kerning on " + self.changed_masters()

    def refresh(self) -> None:
        tool = self.tool
        self.snapshot, self.edits, self.rows, text = None, {}, [], ""
        if tool.package is None:
            self.subtitle.setText("Open a font first.")
        else:
            try:
                self.before_plan()
                self.snapshot = fontui.kerning_snapshot(tool.package, typed=self.TYPED)
                self.edits, self.rows, text = self.plan(self.snapshot)
            except ERRORS as error:
                self.snapshot, self.edits, self.rows = None, {}, []
                text = f"{tool.app}: {error}"
        self.grid.set_rows(self.rows)
        self.count.setText(text)
        self.apply_button.setEnabled(self.ready())

    def before_plan(self) -> None:
        """Hook for widgets that depend on the masters (scope and source combos)."""

    def ready(self) -> bool:
        return any(self.edits.values())

    def changed(self) -> int:
        return sum(len(changes) for changes in self.edits.values())

    def row_chosen(self, name: str, master: Any) -> None:
        left, _, right = name.partition("  ")
        self.tool.show_pair(left, right, master)

    def apply(self) -> bool:
        """Write the displayed plan as one Undo step, then re-read and report."""
        edits, snapshot = self.edits, self.snapshot

        def write() -> bool:
            done = self.tool.write(self.UNDO or self.ACTION, self.subject(), edits, snapshot)
            self.tool.reload()
            self.tool.say(self.result(edits) if done else f"{self.tool.app}: nothing changed.")
            return done

        done = bool(self.run(write))
        if not done:
            self.snapshot, self.edits, self.rows = None, {}, []
            self.grid.set_rows([])
            self.apply_button.setEnabled(False)
        return done


__all__ = ["CheckTable", "Panel", "PlanPanel", "button", "check", "clipboard", "combo", "get", "label",
           "line_edit", "row", "spin"]
