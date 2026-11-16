# this_file: src/fontlabapp/fontui/hint_tools.py
# SPDX-License-Identifier: Apache-2.0
"""Two hint tasks in the shared shell with a read-only glyph canvas."""
from types import SimpleNamespace
from typing import Any

from PythonQt import QtGui

import fontlabapp.fontui as fontui
from fontlabapp.core import scripting
from fontlabapp.fontui.appshell import AppShell
from fontlabapp.fontui.lifecycle import Owned

from fontlabapp.qt.widgets import _cleanup_failure
from fontlabapp.hints.postscript import hint_counts

from fontlabapp.studios.hint_tools.session import Session


class HintTab(Owned):
    """Explicit hint direction/scope controls and a sortable captured-target table."""

    def __init__(self, shell: Any, session: Session, mode: str) -> None:
        super().__init__(shell.widget)
        self.shell, self.session, self.mode = shell, session, mode
        self.all_masters = QtGui.QCheckBox('All masters', self.widget)
        self.bases = QtGui.QCheckBox('Edit bases of automatic composites anyway', self.widget)
        self.horizontal = QtGui.QCheckBox('Horizontal hints', self.widget)
        self.vertical = QtGui.QCheckBox('Vertical hints', self.widget)
        for control in (self.all_masters, self.bases, self.horizontal, self.vertical):
            self.layout.addWidget(control)
        self.horizontal.setChecked(True)
        self.vertical.setChecked(True)
        self.horizontal.setVisible(mode == 'remove')
        self.vertical.setVisible(mode == 'remove')
        help_text = ('Set alignment zones and standard stems in Font Info first. '
                     'The native autohinter can change package hint settings and node links.'
                     if mode == 'autohint' else 'Remove selected PostScript hint directions. TrueType instructions stay unchanged.')
        label = QtGui.QLabel(help_text, self.widget)
        label.setWordWrap(True)
        self.layout.addWidget(label)
        discard = QtGui.QPushButton('Discard preview', self.widget)
        self.layout.addWidget(discard)
        self.connect(discard.clicked, lambda *args: self.discard())
        self.rows = []
        self.table = fontui.glyph_table(['Glyph', 'Master', 'Before H', 'Before V', 'After H', 'After V', 'Result'], self.widget)
        self.layout.addWidget(shell.embed(self.table), 1)
        self.connect(self.table.row_selected, self.row_selected)
        shell.set_actions(self, refresh=self.refresh, preview=self.preview, apply=self.apply,
                          dirty=lambda: self.session.accepted is not None,
                          ready=lambda: self.session.accepted is not None,
                          apply_label='Autohint' if mode == 'autohint' else 'Remove Hints')

    def options(self) -> tuple:
        return (self.mode, bool(self.all_masters.isChecked()), bool(self.bases.isChecked()),
                bool(self.horizontal.isChecked()), bool(self.vertical.isChecked()))

    def discard(self) -> None:
        self.session.accepted = None
        self.rows = []
        self.table.set_rows([])
        self.shell.set_status('Preview discarded; no font data changed.')

    def refresh(self) -> None:
        self.session.refresh()
        self.table.set_rows([])
        self.bases.setChecked(False)
        self.shell.set_status('Selection refreshed. Preview Changes before applying.')

    def preview(self) -> list:
        rows = self.rows = self.session.preview(*self.options())
        self.table.set_rows([(str(r.glyph.name), r.master,
                              (r.master, *r.before, '', '', r.note or 'Ready')) for r in rows])
        self.shell.set_status(f'{len(rows)} layer(s) inspected; nothing written.')
        if rows:
            self.row_selected(str(rows[0].glyph.name), rows[0].master)
        return rows

    def apply(self) -> dict:
        result = self.session.apply(*self.options())
        self.table.set_rows([(str(r.glyph.name), r.master,
                              (r.master, *r.before, *(hint_counts(r.layer) if not r.note else ('', '')),
                               r.note or 'Applied')) for r in self.rows])
        self.shell.set_status(f"{result['layers']} layer(s). " + '; '.join(result.get('mismatches', ()))
                              + ' ' + result.get('pending_note', ''))
        if self.shell.preview is not None:
            self.shell.preview.refresh()
        return result

    def row_selected(self, name: str, layer: str | None = None) -> None:
        try:
            self.session.package()
            if self.shell.preview is not None:
                self.shell.preview.load(name, layer)
        except (ValueError, RuntimeError) as error:
            self.shell.set_status(str(error))


def show(parent: Any = None, *, package: Any = None, selection: Any = None,
         font: Any = None, preview: Any = None) -> AppShell:
    """Open Hint Tools, capturing one font and independent plans for both tabs."""
    provider = package or scripting.current_package
    shell = AppShell('Hint Tools', 'tglyph', parent=parent, package=provider)
    try:
        for title, mode in (('Autohint', 'autohint'), ('Remove PostScript hints', 'remove')):
            session = Session(provider, selection or scripting.names_selected_names)
            shell.add_tab(SimpleNamespace(title=title, build=lambda app, s=session, m=mode: fontui._construct(HintTab, app, s, m)))
        canvas = preview(shell) if preview else fontui.glyph_view(
            (font or fontui.current_font)(), shell.widget, layer=session.master,
            controls=False, read_only=True, label_prefix='Hint Tools', hint_check=shell.hint_check)
        shell.set_preview(canvas)
        shell.set_about('Hint Tools — Autohint and Remove PostScript hints.\n'
                        'Preview captures the selected glyphs and their explicit master layers.\n'
                        'Source: https://github.com/fontlabcom/fontlab-python-scriptmix\n'
                        'Credits: FontLab sample authors and App contributors. Apache-2.0.')
        shell.show()
    except BaseException as error:
        _cleanup_failure(shell, error)
        raise
    return shell
