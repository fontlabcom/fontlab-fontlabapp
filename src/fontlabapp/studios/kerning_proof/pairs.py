# this_file: src/fontlabapp/studios/kerning_proof/pairs.py
# SPDX-License-Identifier: Apache-2.0
"""Ticked text pairs retain original Set/Add, master scope and explicit-write policy."""

from typing import Any

from PythonQt import QtCore

import fontlabapp.fontui as fontui
from fontlabapp.core.scripting import kerning_selection_api

from fontlabapp.studios._kerning_ui import Panel, button, combo, get, line_edit, row, spin, label


selection = kerning_selection_api()
TITLE = 'Kerning Pairs from Text'


def write_kerning(package: Any, edits: dict) -> None:
    """Retain the original console writer and Undo title."""
    fontui.write_kerning(package, edits, TITLE)


class PairsPanel(Panel):
    """Read effective values, then stage only checked explicit glyph pairs."""

    def __init__(self, tool: Any) -> None:
        super().__init__(tool)
        self.text = line_edit(self.widget, 'AVATAR Type', 'Words or /glyph/name tokens')
        row(self.widget, self.layout, 'Text', self.text)
        self.mode = combo(self.widget, ['Set to', 'Add to current'])
        row(self.widget, self.layout, 'Ticked pairs', self.mode)
        self.value = spin(self.widget, -2000, 2000, 0, suffix=' units')
        row(self.widget, self.layout, 'Value', self.value)
        self.scope = combo(self.widget, ['Current master', 'All masters'])
        row(self.widget, self.layout, 'Masters', self.scope)
        self.grid = self.table(['Pair', *tool.masters], self.row_chosen)
        self.grid.proxy.setSortRole(QtCore.Qt.UserRole)
        button(self.widget, self.layout, 'Discard preview and refresh', self.discard)
        self.snapshot: Any = None
        self.accepted: Any = None
        self.values: dict = {}
        self.pairs: list = []
        self.source_text = ''
        self.filling = False
        self.count_label = label(self.widget, self.layout)
        for signal in (self.grid.model.itemChanged, self.mode.currentIndexChanged,
                       self.value.valueChanged, self.scope.currentIndexChanged):
            tool.shell.connect(signal, lambda *args: self.run(self.count))
        tool.shell.set_actions(self.widget, refresh=self.refresh, preview=self.preview_changes,
                               apply=self.apply, ready=self.ready, dirty=lambda: self.accepted is not None)
        self.reload_view()

    def clear(self) -> None:
        self.snapshot, self.accepted, self.values, self.pairs = None, None, {}, []
        self.grid.set_rows([])

    def refresh(self, keep_ticks: list | None = None) -> None:
        self.clear()
        package = self.tool.shell.package()
        if package is None:
            self.subtitle.setText('Open a font first.')
            self.count()
            return
        before = fontui.kerning_snapshot(package)
        self.source_text = get(self.text.text)
        pairs = selection.adjacent_pairs(selection.parse_words(self.source_text, package))
        values = selection.text_values(package, self.tool.masters, pairs)
        if fontui.kerning_snapshot(package) != before:
            raise ValueError('Kerning changed while reading text pairs; refresh again.')
        self.snapshot, self.pairs, self.values = before, pairs, values
        rows = []
        for pair in pairs:
            cells = [(f'{value:g}' if own else f'{value:g}  class' if value else '–')
                     for master in self.tool.masters for value, own in (values[pair, master],)]
            rows.append(('  '.join(pair), self.tool.current, tuple(cells)))
        self.filling = True
        self.grid.set_rows(rows)
        for index in range(len(pairs)):
            item = self.grid.model.item(index, 0)
            item.setCheckable(True)
            item.setCheckState(QtCore.Qt.Checked if keep_ticks is None or pairs[index] in keep_ticks else QtCore.Qt.Unchecked)
            item.setData('  '.join(pairs[index]), QtCore.Qt.UserRole)
            for column, master in enumerate(self.tool.masters, 1):
                self.grid.model.item(index, column).setData(values[pairs[index], master][0], QtCore.Qt.UserRole)
        self.filling = False
        self.subtitle.setText(f'{len(pairs)} pairs from the text; class values are inherited. Writes create explicit glyph pairs.')
        self.count()

    def ticked(self) -> list:
        return [pair for index, pair in enumerate(self.pairs)
                if self.grid.model.item(index, 0).checkState() == QtCore.Qt.Checked]

    def count(self) -> None:
        if self.filling:
            return
        edits = self.plan()
        cells = sum(len(pairs) for pairs in edits.values())
        self.count_label.setText(f'{len(self.ticked())} of {len(self.pairs)} pairs ticked · {cells} values to write')

    def plan(self) -> dict:
        masters = self.tool.scope(get(self.scope.currentIndex) == 1)
        return selection.text_plan(masters, self.ticked(), self.values,
                                   'add' if get(self.mode.currentIndex) else 'set', get(self.value.value))

    def preview_changes(self) -> None:
        if get(self.text.text) != self.source_text:
            self.refresh()
        self.accepted = self.plan() if self.snapshot is not None else None
        count = sum(len(pairs) for pairs in (self.accepted or {}).values())
        self.tool.say(f'{count} explicit values staged. Apply writes only the ticked pairs.')
        if self.tool.preview is not None:
            self.tool.preview.set_text(self.source_text)

    def ready(self) -> bool:
        return bool(self.accepted) and get(self.text.text) == self.source_text and self.plan() == self.accepted

    def apply(self) -> bool:
        if not self.ready():
            raise ValueError('Preview Changes before applying the current text-pair controls.')
        edits, self.accepted = self.accepted, None
        try:
            result = self.tool.write('Set text pairs', 'on ' + ', '.join(edits), edits, self.snapshot)
        except Exception:
            self.clear()
            raise
        try:
            if self.tool.preview is not None:
                self.tool.preview.refresh()
            keep_ticks = self.ticked()
            self.refresh(keep_ticks)
        except Exception as error:
            self.clear()
            outcome = 'Kerning was applied' if result else 'Kerning unchanged'
            guidance = 'Use Undo and Refresh.' if result else 'Use Refresh.'
            raise RuntimeError(f'{outcome}; preview failed: {error}. {guidance}') from error
        self.tool.say(f'Wrote {sum(len(pairs) for pairs in edits.values())} pair values' if result else 'No values changed.')
        return result

    def failed(self, error: BaseException) -> None:
        self.clear()
        self.tool.say(f'Kerning Proof: {error}. Use Refresh.')
        self.subtitle.setText(self.tool.status)

    def discard(self) -> None:
        self.accepted = None
        self.reload_view()

    def row_chosen(self, text: str, master: Any) -> None:
        left, right = text.split('  ', 1)
        self.tool.show_pair(left, right, master)
