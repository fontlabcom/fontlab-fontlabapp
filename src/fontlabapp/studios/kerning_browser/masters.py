# this_file: src/fontlabapp/studios/kerning_browser/masters.py
# SPDX-License-Identifier: Apache-2.0
"""Kerning Browser Masters tab: Scriptmix Compare Masters ("Compare Kerning Across Masters").

What: one row per explicit pair with its value on every master ("–" where
absent) and its flags: sign (the value changes sign), missing (absent on
some masters) and jump (neighbouring masters differ by more than "Jump
above", 0–1000, default 40 units). Filter by a substring of either side;
"Only flagged" hides clean rows. Read-only: no font edits, no history.
``table`` and ``flags`` are the original bodies.
Used by ``fontlabapp.studios.kerning_browser`` (tab builder).
"""

import itertools
from typing import Any

from PythonQt import QtCore, QtGui

from fontlabapp.core.scripting import kerning_pairs

from .._kerning import Tool
from .._kerning_ui import Panel, SortItem, button, check, get, label, line_edit, spin

TITLE = "Compare Kerning Across Masters"


def table(
    package: Any, masters: list[str]
) -> dict[tuple[str, str], list[float | None]]:
    """{(left, right): [value or None per master]} sorted by pair."""
    per_master = [kerning_pairs(package, m) for m in masters]
    keys = sorted(set().union(*per_master)) if per_master else []
    return {k: [p.get(k) for p in per_master] for k in keys}


def flags(values: list[float | None], threshold: float) -> list[str]:
    """Reasons a row looks inconsistent: 'sign', 'missing', 'jump'."""
    present = [v for v in values if v is not None]
    reasons = []
    if any(v < 0 for v in present) and any(v > 0 for v in present):
        reasons.append("sign")
    if len(present) < len(values):
        reasons.append("missing")
    if any(abs(b - a) > threshold for a, b in itertools.pairwise(present)):
        reasons.append("jump")
    return reasons


class MastersPanel(Panel):
    def __init__(self, tool: Tool) -> None:
        super().__init__(tool)
        controls = QtGui.QHBoxLayout()
        self.layout.addLayout(controls)
        self.search = line_edit(self.widget, placeholder="Filter pairs, e.g. A or @L_", slot=self.contain(self.fill))
        controls.addWidget(self.search, 1)
        label(self.widget, controls, "Jump above")
        self.threshold = spin(self.widget, 0, 1000, 40, suffix=" units", slot=self.contain(self.fill))
        self.threshold.setAccessibleName("Jump above")
        controls.addWidget(self.threshold)
        self.only_flagged = check(self.widget, controls, "Only flagged", False, self.contain(self.fill))
        self.grid = QtGui.QTableWidget(0, 2, self.widget)
        self.grid.setAccessibleName("Pairs")
        self.grid.horizontalHeader().setSectionResizeMode(QtGui.QHeaderView.Interactive)
        self.grid.horizontalHeader().setSortIndicator(0, QtCore.Qt.AscendingOrder)
        self.grid.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
        self.grid.currentCellChanged.connect(self.contain(lambda r, *args: self.pair_chosen(self.grid.item(r, 0).data(QtCore.Qt.UserRole) if r >= 0 else -1)))
        self.layout.addWidget(self.grid, 1)
        buttons = QtGui.QHBoxLayout()
        self.layout.addLayout(buttons)
        button(self.widget, buttons, "Reload", tool.reload)
        self.rows: dict = {}
        self.shown: list[tuple] = []

    def refresh(self) -> None:
        tool = self.tool
        if tool.package is None:
            self.subtitle.setText("Open a font first.")
            self.rows = {}
        else:
            self.rows = table(tool.package, tool.masters)
            self.subtitle.setText(
                f"{len(self.rows)} pairs across {len(tool.masters)} masters. Flags: sign = the value "
                "changes sign, missing = absent on some masters, jump = neighbouring masters "
                "differ by more than the threshold."
            )
        self.fill()

    def fill(self) -> None:
        needle = get(self.search.text).strip()
        threshold = get(self.threshold.value)
        self.shown = []
        for (left, right), values in self.rows.items():
            if needle and needle not in left and needle not in right:
                continue
            reasons = flags(values, threshold)
            if self.only_flagged.isChecked() and not reasons:
                continue
            self.shown.append(((left, right), values, reasons))
        masters = self.tool.masters
        self.grid.setSortingEnabled(False)
        self.grid.setColumnCount(len(masters) + 2)
        self.grid.setHorizontalHeaderLabels(["Pair", *masters, "Flags"])
        self.grid.setRowCount(len(self.shown))
        for number, ((left, right), values, reasons) in enumerate(self.shown):
            item = SortItem(f"{left}  {right}")
            item.setData(QtCore.Qt.UserRole, number)
            self.grid.setItem(number, 0, item)
            for column, value in enumerate(values, 1):
                self.grid.setItem(number, column, SortItem("–" if value is None else f"{value:g}"))
            self.grid.setItem(number, len(values) + 1, SortItem(", ".join(reasons)))
        self.grid.setSortingEnabled(True)
        flagged = sum(1 for values in self.rows.values() if flags(values, threshold))
        if self.tool.package is not None:
            self.tool.say(f"{len(self.shown)} rows shown · {flagged} of {len(self.rows)} pairs flagged")

    def clear(self) -> None:
        self.rows, self.shown = {}, []
        self.grid.setRowCount(0)

    def pair_chosen(self, number: int) -> None:
        if 0 <= number < len(self.shown):
            left, right = self.shown[number][0]
            self.tool.show_pair(left, right, self.tool.current)


__all__ = ["TITLE", "MastersPanel", "flags", "table"]
