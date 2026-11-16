# this_file: src/fontlabapp/studios/kerning_proof/tabs.py
# SPDX-License-Identifier: Apache-2.0
"""Read-only text preview and staged original symmetry with complete diagnostics."""

import json
from typing import Any

from PythonQt import QtGui

from fontlabapp.core.scripting import current_package, kerning_layout
from fontlabapp.studios._kerning_ui import Panel, button, check, combo, get, line_edit, row, spin

from .stage import SymmetryStage
from .text import Canvas, outline, parse_text


class TextPanel(Panel):
    """Control the captured TMetrics without allowing edits through its preview."""

    def __init__(self, tool: Any) -> None:
        super().__init__(tool)
        self.text = line_edit(self.widget, 'AVATAR LTAVA Tyre WAVE /Aacute/V', 'Text or /glyphname tokens')
        row(self.widget, self.layout, 'Text', self.text)
        self.master = combo(self.widget, tool.masters)
        row(self.widget, self.layout, 'Master', self.master)
        if tool.current in tool.masters:
            self.master.setCurrentIndex(tool.masters.index(tool.current))
        self.size = spin(self.widget, 16, 240, 72, suffix=' px')
        row(self.widget, self.layout, 'Size', self.size)
        self.kerned = check(self.widget, self.layout, 'Kerning', True)
        self.show_values = check(self.widget, self.layout, 'Show values', True)
        self.rows, self.paths = [], {}
        self.upm, self.ascender, self.descender = 1000, 800, -200
        self.canvas = Canvas(self)
        self.layout.addWidget(self.canvas, 1)
        self.subtitle.setText('Native outline proof below includes effective kerning on every master.')
        tool.shell.set_actions(self.widget, refresh=self.refresh, preview=self.refresh)
        for signal in (self.text.textChanged, self.master.currentIndexChanged, self.size.valueChanged,
                       self.kerned.toggled):
            tool.shell.connect(signal, lambda *args: self.run(self.refresh))
        tool.shell.connect(self.show_values.toggled, lambda *args: self.canvas.update())

    def ensure_target(self) -> None:
        package = self.tool.package
        if package is not None and current_package(package.id) is None:
            raise ValueError('Results are stale: the original font is no longer current; reopen this tool.')

    def clear(self) -> None:
        self.rows, self.paths = [], {}
        self.canvas.update()

    def refresh(self) -> None:
        self.clear()
        self.ensure_target()
        package = self.tool.package
        if package is not None:
            self.upm = package.upm
            self.ascender, self.descender = package.ascender_value, package.descender_value
            master = get(self.master.currentText)
            rows = kerning_layout(package, parse_text(get(self.text.text), package), master, self.kerned.isChecked())
            paths = {name: outline(package.findName(name).findLayer(master)) for name, *_ in rows}
            self.ensure_target()
            self.rows, self.paths = rows, paths
            kerned = [row for row in rows if row[3]]
            self.subtitle.setText(f"{master} master · glyph outlines with {'kerning applied' if self.kerned.isChecked() else 'kerning off'}")
            self.tool.say(f'{len(rows)} glyphs · {len(kerned)} kerned gaps, {sum(row[3] for row in kerned):g} units in total')
        else:
            self.subtitle.setText('Open a font first.')
        self.canvas.update()
        preview = self.tool.preview
        if preview is not None:
            preview.set_layer(get(self.master.currentText))
            preview.set_text(get(self.text.text))
            preview.set_view(size=get(self.size.value), kerning=self.kerned.isChecked())
            preview.refresh()


class SymmetryPanel(Panel):
    """All original configured targets, class choices, warnings and master counts."""

    def __init__(self, tool: Any) -> None:
        super().__init__(tool)
        self.stage = SymmetryStage(tool.shell.package)
        self.table = self.table(['Pair', 'Master', 'Before', 'Requested', 'Warning'], self.row_chosen)
        self.details = QtGui.QPlainTextEdit(self.widget)
        self.details.setReadOnly(True)
        self.details.setAccessibleName('Complete symmetry diagnostics')
        self.layout.addWidget(self.details)
        self.subtitle.setText('Preview all Science Gothic targets. Apply checks unchanged glyphs, classes and kerning.')
        button(self.widget, self.layout, 'Discard symmetry preview', self.discard)
        tool.shell.set_actions(self.widget, refresh=self.discard, preview=self.preview_changes,
                               apply=self.apply, ready=self.stage.ready, dirty=self.stage.ready,
                               apply_label='Apply Symmetry')

    def refresh(self) -> None:
        self.discard()

    def discard(self) -> None:
        self.stage.before, self.stage.result = None, None
        self.table.set_rows([])
        self.details.setPlainText('')

    def render(self, report: dict) -> None:
        self.details.setPlainText(json.dumps(report, indent=2, ensure_ascii=False))
        rows = [('  '.join(item['glyph_pair']), master['master'],
                 (master['master'], str(item['before']), item['requested_value'],
                  'Missing direction' if item['warning'] else ''))
                for master in report['masters'] for item in master['mismatches']]
        self.table.set_rows(rows)
        self.tool.say('Symmetry applied.' if report['applied'] else f'{len(rows)} symmetry comparisons differ; preview makes no changes.')

    def preview_changes(self) -> None:
        self.discard()
        self.render(self.stage.preview())

    def apply(self) -> None:
        self.render(self.stage.apply())
        if self.tool.preview is not None:
            self.tool.preview.refresh()

    def row_chosen(self, text: str, master: Any) -> None:
        left, right = text.split('  ', 1)
        self.tool.show_pair(left, right, master)
