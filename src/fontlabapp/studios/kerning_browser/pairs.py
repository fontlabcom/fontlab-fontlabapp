# this_file: src/fontlabapp/studios/kerning_browser/pairs.py
# SPDX-License-Identifier: Apache-2.0
"""Kerning Browser Pairs tab: Scriptmix Pair List Browser ("Kerning Pairs").

What: every explicit pair of one master (default the current master) in
stable name order, with the original filter (substring of either side;
``=name`` must equal a whole side). Choosing a row previews the pair. "Export
CSV…" writes the shown rows as ``left,right,value,master`` (value ``:g``).
Read-only: no font edits, no history. ``matches``, ``filtered`` and
``export_csv`` are the original bodies.
Used by ``fontlabapp.studios.kerning_browser`` (tab builder).
"""

import csv
import pathlib
from typing import Any

from PythonQt import QtGui

import fontlabapp.fontui as fontui
from fontlabapp.core.scripting import kerning_pairs

from .._kerning import Tool
from .._kerning_ui import Panel, button, combo, get, line_edit, row

TITLE = "Kerning Pairs"


def matches(pair: tuple[str, str], text: str) -> bool:
    """Filter rule: substring of either side; '=name' must equal a whole side."""
    text = text.strip()
    if not text:
        return True
    if text.startswith("="):
        return text[1:] in pair
    return any(text in side for side in pair)


def filtered(
    pairs: dict[tuple[str, str], float], text: str
) -> list[tuple[str, str, float]]:
    """Return matching explicit pairs in stable name order."""
    return sorted((l, r, v) for (l, r), v in pairs.items() if matches((l, r), text))  # noqa: E741 - original body


def export_csv(
    rows: list[tuple[str, str, float]], master: str, path: str | pathlib.Path
) -> int:
    """Write left,right,value,master rows; returns the number of pairs written."""
    with pathlib.Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["left", "right", "value", "master"])
        for left, right, value in rows:
            writer.writerow([left, right, f"{value:g}", master])
    return len(rows)


class PairsPanel(Panel):
    def __init__(self, tool: Tool) -> None:
        super().__init__(tool)
        self.master = row(self.widget, self.layout, "Master", combo(self.widget, [], self.contain(self.show_rows)))
        self.filter = line_edit(self.widget, placeholder="Filter: T, @L_A, =V …", slot=self.contain(self.show_rows))
        self.layout.addWidget(self.filter)
        self.grid = self.table(["Left", "Right", "Value"], self.row_chosen)
        buttons = QtGui.QHBoxLayout()
        self.layout.addLayout(buttons)
        button(self.widget, buttons, "Refresh", tool.reload)
        self.export_button = button(self.widget, buttons, "Export CSV…", lambda: self.run(self.export))
        self.pairs: dict = {}
        self.rows: list[tuple[str, str, float]] = []
        self.dialog: Any = None
        self.snapshot: Any = None
        self.last_export: Any = None

    def chosen(self) -> str:
        index = get(self.master.currentIndex)
        return self.tool.masters[index] if 0 <= index < len(self.tool.masters) else ""

    def refresh(self) -> None:
        tool = self.tool
        previous = self.chosen() if get(self.master.count) else tool.current
        self.master.blockSignals(True)
        self.master.clear()
        for name in tool.masters:
            self.master.addItem(name)
        if previous in tool.masters:
            self.master.setCurrentIndex(tool.masters.index(previous))
        self.master.blockSignals(False)
        self.show_rows()

    def show_rows(self) -> None:
        tool, master = self.tool, self.chosen()
        self.snapshot = fontui.kerning_snapshot(tool.package) if tool.package is not None else None
        self.pairs = kerning_pairs(tool.package, master) if tool.package is not None and master else {}
        text = get(self.filter.text)
        self.rows = filtered(self.pairs, text)
        if tool.package is None:
            self.subtitle.setText("Open a font first.")
        else:
            classes = sum(1 for a, b in self.pairs if a.startswith("@") or b.startswith("@"))
            self.subtitle.setText(f"{master}: {len(self.pairs)} pairs, {classes} of them with a class side")
        self.grid.set_rows([(a, master, (b, v)) for a, b, v in self.rows])
        self.export_button.setEnabled(bool(self.rows))
        if tool.package is not None:
            tool.say(f"{len(self.rows)} of {len(self.pairs)} pairs" if text.strip() else f"{len(self.pairs)} pairs")

    def row_chosen(self, name: str, master: Any) -> None:
        """Preview the chosen row's pair (first column left side, second column right side) on its master."""
        row = self.grid.current_row()
        if row is not None:
            self.tool.show_pair(row.glyph_name, row.values[0], master)

    def clear(self) -> None:
        self.pairs, self.rows, self.snapshot = {}, [], None
        self.grid.set_rows([])
        self.export_button.setEnabled(False)

    def export(self) -> None:
        """Ask for a file without blocking FontLab, then write the shown rows."""
        self.check_source()
        dialog = self.dialog
        if dialog is None:
            dialog = self.dialog = QtGui.QFileDialog(self.widget, "Export kerning pairs")
            dialog.setAcceptMode(QtGui.QFileDialog.AcceptSave)
            dialog.setNameFilter("CSV files (*.csv)")
            dialog.setDefaultSuffix("csv")
            dialog.selectFile(f"kerning-{self.chosen()}.csv")
            self.tool.shell.connect(dialog.fileSelected, lambda path: self.run(lambda: self.write(path)))
        dialog.open()

    def check_source(self) -> None:
        self.tool.shell.package()
        if self.snapshot is None or fontui.kerning_snapshot(self.tool.package) != self.snapshot:
            raise ValueError("Kerning results are stale; refresh before exporting.")

    def write(self, path: str) -> int:
        self.check_source()
        rows = [self.rows[self.grid.proxy.mapToSource(self.grid.proxy.index(n, 0)).row()]
                for n in range(self.grid.proxy.rowCount())]
        count = export_csv(rows, self.chosen(), path)
        self.last_export = {"path": path, "pairs": count}
        self.tool.say(f"Exported {count} pairs to {pathlib.Path(path).name}")
        return count


__all__ = ["TITLE", "PairsPanel", "export_csv", "filtered", "matches"]
