# this_file: src/fontlabapp/fontui/outline_compatibility.py
# SPDX-License-Identifier: Apache-2.0
"""Contour order, exact cubic promotion and node counts in one captured-font shell."""
from typing import Any

from PythonQt import QtGui

import fontlabapp.fontui as fontui
from fontlabapp.core import scripting
from fontlabapp.proof.inspectors import model as readers
from fontlabapp.proof.inspectors.views import OrderView
from fontlabapp.qt.widgets import _cleanup_failure
from fontlabapp.studios import TabSpec
from fontlabapp.studios.outline_doctor.session import Doctor
from fontlabapp.fontui.outline_compatibility_routes import compatible

from .lifecycle import Owned
from .outline_editing import OperationTab, native_check


class ReadTab(Owned):
    """Read the captured font; select only flags from the exact displayed snapshot."""

    def __init__(self, shell: Any, studio: Doctor, mode: str, selection: Any):
        super().__init__(shell.widget)
        self.shell, self.studio, self.mode = shell, studio, mode
        self.names = tuple(selection())
        self.accepted = None
        self.flagged = []
        self.glyph = QtGui.QComboBox(self.widget)
        self.glyph.addItems(list(self.names))
        self.glyph.setAccessibleName('Glyph')
        self.whole = QtGui.QCheckBox('Whole font', self.widget)
        self.only_flagged = QtGui.QCheckBox('Show flagged glyphs only', self.widget)
        for widget in (self.glyph, self.whole, self.only_flagged):
            self.layout.addWidget(widget)
        self.glyph.setVisible(mode == 'order')
        self.whole.setVisible(mode == 'statistics')
        self.only_flagged.setVisible(mode == 'statistics')
        headers = ('Glyph', 'Master', 'Contour', 'Start X', 'Start Y', 'Direction', 'Nodes') if mode == 'order' else ('Glyph', 'Master', 'Contours', 'Nodes', 'Status')
        self.table = fontui.glyph_table(headers, self.widget)
        self.layout.addWidget(shell.embed(self.table), 1)
        self.connect(self.table.row_selected, self.row_selected)
        if mode == 'order':
            self.view = OrderView(self.widget)
            self.view.report = shell.set_status
            self.view.before_draw = self.ensure_current
            self.layout.addWidget(self.view, 1)
            help_text = '● start node · number = contour order · arrow = first-segment direction'
        else:
            help_text = 'Matching counts alone do not prove matching contour structure.'
        label = QtGui.QLabel(help_text, self.widget)
        label.setWordWrap(True)
        self.layout.addWidget(label)
        shell.set_actions(self, refresh=self.refresh, preview=self.refresh,
                          apply=self.select_flagged if mode == 'statistics' else None,
                          ready=lambda: self.accepted is not None and bool(self.flagged),
                          apply_label='Select Flagged')
        for signal in (self.glyph.currentIndexChanged, self.whole.toggled, self.only_flagged.toggled):
            self.connect(signal, lambda *args: self.guard_refresh())

    def read(self) -> tuple:
        package = self.studio.package()
        names = readers.all_names(package) if self.whole.isChecked() else self.names
        rows, flagged, columns, sources = [], [], [], []
        if self.mode == 'order':
            value = self.glyph.currentText
            names = [str(value() if callable(value) else value)]
        for name in names:
            if not name:
                continue
            glyph = self.studio.native_glyph(name)
            counts = readers.glyph_counts(glyph, self.studio.masters)
            bad = readers.incompatible(counts)
            if bad:
                flagged.append(name)
            sources.append((name, counts))
            for master, layer in readers.master_layers(glyph, self.studio.masters).items():
                if self.mode == 'order':
                    info = [] if layer.autoLayer else readers.contour_info(layer)
                    columns.append((master + (' (auto)' if layer.autoLayer else ''), info))
                    rows.extend((name, master, (master, index, *start, direction, len(points)))
                                for index, points, start, _, direction in info)
                elif not self.only_flagged.isChecked() or bad:
                    count = counts[master]
                    rows.append((name, master, (master, *(count if count is not None else ('auto', 'auto')),
                                               '✗ differ' if bad else '✓')))
        token = (tuple(names), self.whole.isChecked(), self.only_flagged.isChecked(), sources, columns)
        return rows, flagged, columns, token

    def refresh(self) -> None:
        self.accepted = None
        rows, flagged, columns, token = self.read()
        if token != self.read()[3]:
            raise ValueError('Sources changed during refresh; refresh again.')
        self.table.set_rows(rows)
        self.flagged, self.accepted = flagged, token
        if self.mode == 'order':
            self.view.columns = columns
            self.view.update()
        self.shell.set_status(f'{len(rows)} rows; {len(flagged)} glyphs have differing counts. No outlines changed.')
        if rows:
            self.row_selected(rows[0][0], rows[0][1])

    def guard_refresh(self) -> None:
        try:
            self.refresh()
        except Exception as error:
            self.accepted = None
            self.shell.set_status(str(error))

    def ensure_current(self) -> None:
        if self.accepted is None or self.read()[3] != self.accepted:
            raise ValueError('Displayed sources changed; Refresh before using these results.')

    def select_flagged(self) -> list[str]:
        self.ensure_current()
        selected = scripting.select_glyphs(self.flagged, package_id=int(self.studio.package().id))
        self.shell.set_status(f'Selected {len(selected)} flagged glyphs in the Font window.')
        return selected

    def row_selected(self, name: str, layer: str) -> None:
        try:
            self.ensure_current()
            self.studio.preview.load(name, layer)
        except Exception as error:
            self.shell.set_status(str(error))


def show(parent: Any = None, *, package: Any = None, selection: Any = None,
         font: Any = None, preview: Any = None) -> Any:
    """Open three tasks with exact original policies and a read-only TGlyph."""
    provider = package or scripting.current_package
    selected = selection or scripting.names_selected_names
    bound = provider()
    if bound is None:
        raise ValueError('Open a font first.')
    identity, masters, master = bound.id, tuple(bound.masters), str(bound.master)

    def captured() -> Any:
        current = provider()
        if current is None or current.id != identity:
            raise ValueError('The font changed; reopen Outline Compatibility.')
        if tuple(current.masters) != masters or str(current.master) != master:
            raise ValueError('The master changed; reopen Outline Compatibility.')
        return current

    shell = fontui.app_shell('Outline Compatibility', 'tglyph', parent=parent, package=captured)
    try:
        current_font = (font or fontui.current_font)()
        studio = Doctor(shell, font=lambda: current_font, selection=selected)
        studio.APP = 'Outline Compatibility'
        studio.reload()
        studio.preview = (preview or _preview)(shell, studio)
        shell.set_preview(studio.preview)
        shell.read_tabs = []
        order = fontui._construct(ReadTab, shell, studio, 'order', selected)
        shell.add_tab(TabSpec('Contour Order View', lambda owner: order))
        shell.read_tabs.append(order)
        operation = native_check('make_compatible', 'Make Compatible',
            lambda layer, values, context: compatible.changes(studio.native_glyph(context.glyph), context.master, layer, list(studio.masters)),
            compatible.CompatibleEditor())
        tab = shell.compatible_tab = OperationTab(studio, operation)
        shell.add_tab(TabSpec('Make Compatible', lambda owner: tab.widget))
        stats = fontui._construct(ReadTab, shell, studio, 'statistics', selected)
        shell.add_tab(TabSpec('Node Statistics', lambda owner: stats))
        shell.read_tabs.append(stats)
        studio.reload()
        order.refresh()
        stats.refresh()
        shell.set_about('Outline Compatibility\nCompare contour order and starts; preview cubic promotions before Apply Changes.\n'
                        'Node Statistics selects flagged glyphs without editing outlines.\n'
                        'FontLab sample inspectors: Apache-2.0. Make Compatible: independent adaptation after Simon Cozens (2017), MIT.\n'
                        'https://github.com/simoncozens/GlyphsScripts\nhttps://github.com/fontlabcom/fontlab-python-scriptmix\n'
                        'Full credits and terms: Scriptmix NOTICE and LICENSES.')
        shell.show()
    except BaseException as error:
        _cleanup_failure(shell, error)
        raise
    return shell


def _preview(shell: Any, studio: Doctor) -> Any:
    return fontui.glyph_view(studio.font(), shell.widget, layer=studio.current,
                             controls=False, read_only=True, label_prefix=studio.APP)
