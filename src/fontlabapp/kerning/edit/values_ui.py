# this_file: src/fontlabapp/kerning/edit/values_ui.py
# SPDX-License-Identifier: Apache-2.0
"""Render the complete shared Scale/Round previews and publish batch counts."""

from typing import Any

from fontlabapp import _native
from fontlabapp.glyphs.names.ui import QtCore, QtGui
from fontlabapp.core.scripting import kerning_pairs

fontlab = _native("fontlab")


def refresh_values(self: Any) -> None:
    """Render preview values and counts; enable Apply only for actual staged edits."""
    if self.package is None:
        self.subtitle.setText("Open a font first.")
        self.todo = {}
    else:
        self.todo = self.plan()
        total = sum(len(kerning_pairs(self.package, m)) for m in self.chosen_masters())
        self.subtitle.setText(
            f"{total} pairs in {len(self.chosen_masters())} master{('s' if len(self.chosen_masters()) != 1 else '')}. "
            + self.explain()
        )
    rows = [
        (f"{l}  {r}", m, old, new)
        for (m, items) in self.todo.items()
        for ((l, r), (old, new)) in sorted(items.items())
    ]
    accent = QtGui.QColor(self.palette.color(QtGui.QPalette.Link))
    warn = QtGui.QColor("#d33")
    self.table.setRowCount(len(rows))
    for row, (pair, master, old, new) in enumerate(rows):
        self.table.setItem(row, 0, QtGui.QTableWidgetItem(pair))
        self.table.setItem(row, 1, QtGui.QTableWidgetItem(master))
        for column, value in (
            (2, f"{old:g}"),
            (3, "removed" if new is None else f"{new:g}"),
        ):
            item = QtGui.QTableWidgetItem(value)
            item.setTextAlignment(int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter))
            if column == 3:
                bold = item.font()
                bold.setBold(True)
                item.setFont(bold)
                item.setForeground(QtGui.QBrush(warn if new is None else accent))
            self.table.setItem(row, column, item)
    counts = " · ".join(f"{m} {len(v)}" for (m, v) in self.todo.items())
    self.status.setText(
        f"{len(rows)} pairs change ({counts})" if rows else "Nothing to change"
    )
    self.apply_button.setEnabled(bool(rows))


def apply_values(self: Any, title: str) -> None:
    """Write the complete displayed batch, refresh its baseline and report counts."""
    todo = self.plan()
    edits = {
        m: {pair: new for (pair, (_, new)) in items.items()}
        for (m, items) in todo.items()
        if items
    }
    if edits:
        self.write_edits(edits, title)
    self.last_result = {m: len(items) for (m, items) in todo.items()}
    fontlab.UpdateAll()
    self.refresh_after_apply(self.refresh)
    self.status.setText(
        f"Changed {sum(self.last_result.values())} pairs ("
        + " · ".join(f"{m} {n}" for (m, n) in self.last_result.items())
        + ")"
    )
