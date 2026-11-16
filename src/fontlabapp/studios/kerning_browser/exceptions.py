# this_file: src/fontlabapp/studios/kerning_browser/exceptions.py
# SPDX-License-Identifier: Apache-2.0
"""Kerning Browser Exceptions tab: Scriptmix Exceptions Finder ("Kerning Exceptions").

What: list every explicit pair that overrides a broader class pair on the
current master (default) or all masters, with the class value and the
difference ("same" when redundant). Scanning and ticking change nothing.
"Tick redundant" ticks rows equal to their class value, "Untick all" clears,
"Remove ticked" deletes exactly the ticked exceptions (the shared
``kerning.selection.exception_plan``) as one ``Kerning Browser: Remove <n>
exception(s)`` Undo step, written against the snapshot taken with the scan.
This is the only Kerning Browser tab that edits the font.
Used by ``fontlabapp.studios.kerning_browser`` (tab builder).
"""

from typing import Any

from PythonQt import QtCore, QtGui

import fontlabapp.fontui as fontui

from .._kerning import Tool
from .._kerning_ui import CheckTable, Panel, button, get

TITLE = "Kerning Exceptions"


def cells(row: tuple) -> tuple:
    """Table texts of a ``(master, pair, value, broader, broader_value)`` row."""
    master, pair, value, broader, broader_value = row
    delta = value - broader_value
    return (f"{pair[0]}  {pair[1]}", master, f"{value:g}", f"{broader[0]}  {broader[1]}",
            f"{broader_value:g}", "same" if not delta else f"{delta:+g}")


def write_kerning(package: Any, edits: dict) -> None:
    """Retain the original console writer label and shared guarded batch."""
    fontui.write_kerning(package, edits, TITLE)


class ExceptionsPanel(Panel):
    def __init__(self, tool: Tool) -> None:
        super().__init__(tool)
        form = QtGui.QHBoxLayout()
        self.layout.addLayout(form)
        self.scope = self.scope_box(form)
        self.tick_redundant = button(self.widget, form, "Tick redundant", lambda: self.tick(lambda r: r[2] == r[4]))
        button(self.widget, form, "Untick all", lambda: self.tick(lambda r: False))
        self.grid = CheckTable(self.widget, self.layout,
                               ["Exception", "Master", "Value", "Overrides", "Class value", "Δ"], self.count)
        self.grid.view.currentCellChanged.connect(self.contain(lambda r, *args: self.pair_chosen(
            self.grid.view.item(r, 0).data(QtCore.Qt.UserRole) if r >= 0 else -1)))
        buttons = QtGui.QHBoxLayout()
        self.layout.addLayout(buttons)
        button(self.widget, buttons, "Refresh", tool.reload)
        self.apply_button = button(self.widget, buttons, "Remove ticked", self.apply)
        self.rows: list[tuple] = []
        self.snapshot: Any = None
        tool.shell.set_actions(self.widget, refresh=tool.reload, preview=self.count,
                               apply=self.apply, ready=lambda: self.snapshot is not None and bool(self.ticked()),
                               dirty=lambda: bool(self.ticked()), apply_label="Remove ticked exceptions")

    def refresh(self) -> None:
        """Re-scan (read-only): one snapshot, then the exception rows of the chosen masters."""
        tool = self.tool
        if self.ticked():
            tool.say("Ticked exceptions kept. Remove them or Untick all before refreshing.")
            return
        self.fill_scope(self.scope)
        self.rows, self.snapshot = [], None
        if tool.package is None:
            self.subtitle.setText("Open a font first.")
        else:
            self.snapshot = fontui.kerning_snapshot(tool.package)
            self.rows = tool.backends().selection.find(tool.package, tool.scope(get(self.scope.currentIndex) == 1))
            redundant = sum(1 for r in self.rows if r[2] == r[4])
            self.subtitle.setText(
                f"{len(self.rows)} exceptions, {redundant} of them redundant (same value as the class pair "
                "they override). Tick the ones to delete."
            )
        self.grid.set_rows([cells(r) for r in self.rows])
        self.count()

    def clear(self) -> None:
        """No rows and no snapshot: Remove ticked stays disabled until a scan succeeds."""
        self.rows, self.snapshot = [], None
        self.grid.set_rows([])
        self.apply_button.setEnabled(False)
        self.tick_redundant.setEnabled(False)

    def ticked(self) -> list[tuple]:
        return [self.rows[n] for n in self.grid.ticked()]

    def tick(self, rule: Any) -> None:
        self.grid.set_ticked({n for n, r in enumerate(self.rows) if rule(r)})

    def count(self) -> None:
        ticked = self.ticked()
        self.tool.say(f"{len(ticked)} of {len(self.rows)} ticked" if self.rows else "No exceptions found")
        self.apply_button.setEnabled(bool(ticked))
        self.tick_redundant.setEnabled(any(r[2] == r[4] for r in self.rows))

    def pair_chosen(self, number: int) -> None:
        if 0 <= number < len(self.rows):
            master, pair = self.rows[number][:2]
            self.tool.show_pair(pair[0], pair[1], master)

    def apply(self) -> bool:
        """Delete exactly the ticked exceptions as one Undo step."""
        tool, ticked, snapshot = self.tool, self.ticked(), self.snapshot

        done = False
        try:
            tool.shell.package()
            edits = tool.backends().selection.exception_plan(ticked)
            total = sum(len(p) for p in edits.values())
            done = tool.write("Remove", f"{total} exception{'s' if total != 1 else ''}", edits, snapshot)
            self.grid.set_ticked(set())
            self.refresh()
            if tool.preview is not None:
                tool.preview.refresh()
            tool.say(f"Removed {total if done else 0} exceptions")
            return done
        except (ValueError, RuntimeError, TypeError, AttributeError, TimeoutError) as error:
            self.clear()
            prefix = "Kerning was applied; preview failed. Use Edit > Undo or Refresh. " if done else ""
            tool.say(prefix + str(error))
            return False



__all__ = ["TITLE", "ExceptionsPanel", "cells"]
