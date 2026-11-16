# this_file: src/fontlabapp/studios/kerning_browser/classes.py
# SPDX-License-Identifier: Apache-2.0
"""Kerning Browser Classes tab: Scriptmix Classes Browser ("Kerning Classes").

What: the current master's kerning classes with their side and member count,
filtered by class name (any case) or an exact member glyph name; the chosen
class shows its members and every pair using it with its value on each
master ("–" where absent). "Select members" selects the members in the Font
window. Read-only: no font edits, no history. ``SIDES``, ``pairs_using`` and
``matches`` are the original bodies.
Used by ``fontlabapp.studios.kerning_browser`` (tab builder).
"""

from typing import Any

from PythonQt import QtCore, QtGui

from fontlabapp.core.scripting import kerning_classes, kerning_pairs

from .._kerning import Tool
from .._kerning_ui import Panel, SortItem, button, get, label, line_edit

TITLE = "Kerning Classes"
SIDES = {"KernLeft": "left", "KernRight": "right", "KernBothSide": "both"}


def pairs_using(package: Any, masters: list[str], name: str) -> dict:
    """{(left, right): {master: value}} for pairs with @name on either side."""
    tag, rows = "@" + name, {}
    for master in masters:
        for (left, right), value in kerning_pairs(package, master).items():
            if tag in {left, right}:
                rows.setdefault((left, right), {})[master] = value
    return rows


def matches(name: str, members: list[str], text: str) -> bool:
    """Class name contains the text (any case), or a member is exactly the text (glyph names are case-sensitive)."""
    text = text.strip()
    return not text or text.lower() in name.lower() or text in members


class ClassesPanel(Panel):
    def __init__(self, tool: Tool) -> None:
        super().__init__(tool)
        self.filter = line_edit(self.widget, placeholder="Filter by class name or member glyph", slot=self.contain(self.show_list))
        self.layout.addWidget(self.filter)
        self.list = QtGui.QListWidget(self.widget)
        self.list.setAccessibleName("Classes")
        self.list.currentRowChanged.connect(self.contain(self.show_class))
        self.layout.addWidget(self.list, 1)
        self.title = label(self.widget, self.layout, "No class")
        self.members = label(self.widget, self.layout)
        self.pairs = QtGui.QTableWidget(0, 1, self.widget)
        self.pairs.setAccessibleName("Pairs")
        self.pairs.horizontalHeader().setSectionResizeMode(QtGui.QHeaderView.Interactive)
        self.pairs.horizontalHeader().setSortIndicator(0, QtCore.Qt.AscendingOrder)
        self.pairs.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
        self.pairs.currentCellChanged.connect(self.contain(lambda r, *args: self.pair_chosen(self.pairs.item(r, 0).data(QtCore.Qt.UserRole) if r >= 0 else -1)))
        self.layout.addWidget(self.pairs, 1)
        buttons = QtGui.QHBoxLayout()
        self.layout.addLayout(buttons)
        button(self.widget, buttons, "Refresh", tool.reload)
        self.select_button = button(self.widget, buttons, "Select members", lambda: self.run_selection())
        self.classes: dict = {}
        self.names: list[str] = []
        self.selected: str | None = None
        self.pair_rows: list[tuple[str, str]] = []

    def refresh(self) -> None:
        tool = self.tool
        self.classes = kerning_classes(tool.package, tool.current) if tool.package is not None else {}
        self.show_list()

    def show_list(self) -> None:
        tool, text = self.tool, get(self.filter.text)
        self.names = sorted(n for n, (members, _) in self.classes.items() if matches(n, members, text))
        if tool.package is None:
            self.subtitle.setText("Open a font first.")
        else:
            counts = {s: sum(1 for _, side in self.classes.values() if side == s) for s in ("left", "right", "both")}
            self.subtitle.setText(
                f"{len(self.classes)} classes: {counts['left']} left, {counts['right']} right, "
                f"{counts['both']} both sides. Values are shown for all {len(tool.masters)} masters."
            )
        self.list.blockSignals(True)
        self.list.clear()
        for name in self.names:
            members, side = self.classes[name]
            self.list.addItem(f"@{name}   {side} · {len(members)}")
        self.list.blockSignals(False)
        if tool.package is not None:
            tool.say(f"{len(self.names)} of {len(self.classes)} classes")
        if self.names:
            self.list.setCurrentRow(0)
            self.show_class(0)
        else:
            self.show_class(-1)

    def show_class(self, number: int) -> None:
        """Show the class members and every master's pair values."""
        tool = self.tool
        if number < 0 or number >= len(self.names):
            self.selected = None
            self.title.setText("No class")
            self.members.setText("")
            self.pairs.setRowCount(0)
            self.select_button.setEnabled(False)
            return
        name = self.names[number]
        members, side = self.classes[name]
        self.selected = name
        self.title.setText(f"@{name} · {side} side")
        self.members.setText(" ".join(members))
        rows = pairs_using(tool.package, tool.masters, name)
        self.pair_rows = sorted(rows)
        self.pairs.setSortingEnabled(False)
        self.pairs.setColumnCount(1 + len(tool.masters))
        self.pairs.setHorizontalHeaderLabels(["Pair", *tool.masters])
        self.pairs.setRowCount(len(rows))
        for r, pair in enumerate(self.pair_rows):
            item = SortItem(f"{pair[0]}  {pair[1]}")
            item.setData(QtCore.Qt.UserRole, r)
            self.pairs.setItem(r, 0, item)
            for column, master in enumerate(tool.masters, 1):
                value = rows[pair].get(master)
                self.pairs.setItem(r, column, SortItem("–" if value is None else f"{value:g}"))
        self.pairs.setSortingEnabled(True)
        self.select_button.setEnabled(True)
        tool.say(f"@{name}: {len(members)} members, used in {len(rows)} pairs")

    def clear(self) -> None:
        self.classes, self.names = {}, []
        self.list.clear()
        self.show_class(-1)

    def select_class(self, name: str) -> None:
        """Show a class by name (used by tests and handy from the console)."""
        self.list.setCurrentRow(self.names.index(name))
        self.show_class(self.names.index(name))

    def pair_chosen(self, number: int) -> None:
        if 0 <= number < len(self.pair_rows):
            self.tool.show_pair(*self.pair_rows[number], self.tool.current)

    def run_selection(self) -> None:
        """Clear stale results when the captured target cannot be selected."""
        try:
            self.tool.shell.package()
            self.select_members()
        except (RuntimeError, ValueError) as error:
            self.clear()
            self.tool.say(str(error))

    def select_members(self) -> None:
        if self.selected is None:
            return
        members = self.classes[self.selected][0]
        self.tool.select(members)
        self.tool.say(f"Selected {len(members)} glyphs of @{self.selected} in the Font window")


__all__ = ["SIDES", "TITLE", "ClassesPanel", "matches", "pairs_using"]
