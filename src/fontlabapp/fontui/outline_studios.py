# this_file: src/fontlabapp/fontui/outline_studios.py
# SPDX-License-Identifier: Apache-2.0
# Original MIT provenance and attribution remain in NOTICE and immutable Scriptmix records.
"""S13/S14 shell composition retaining each original native target policy."""
import importlib
from typing import Any

from PythonQt import QtCore, QtGui

import fontlabapp.fontui as fontui
from fontlabapp.qt.properties import value
from fontlabapp.qt.widgets import _cleanup_failure
from fontlabapp.studios import TabSpec
from fontlabapp.studios.transform_studio.actions import capture
from fontlabapp.studios.transform_studio.native import snapshot
from fontlabapp.studios.transform_studio.session import Studio
from .lifecycle import Owned

PANELS = {
    'Transform Studio': (('Transform', 'transform', 'TransformOutlines'),
        ('Slant', 'slant', 'SlantOutlines'), ('Smart Slant', 'smart_slant', 'SmartPanel'),
        ('Rotate Selection', 'rotate_selection', 'SelectionPanel'),
        ('Reflect Horizontally', 'reflect_horizontally', 'SelectionPanel'),
        ('Reflect Vertically', 'reflect_vertically', 'SelectionPanel')),
    'Align and Nudge': (('Align And Distribute', 'align_and_distribute', 'GeometryPanel'),
        ('Superaligner', None, 'ToolPanel'),
        ('Interpolated Nudge', 'interpolated_nudge', 'ToolPanel'),
        ('Overlap Nodes', 'overlap_nodes', 'SelectionPanel')),
}


class OutlineTask(Owned):
    """Embed original controls and writer; the shell alone authorizes Apply."""

    def __init__(self, studio: Any, panel_class: type) -> None:
        super().__init__(studio.shell.widget)
        self.studio, self.accepted, self._panel_closed = studio, None, False
        owner = self

        class Embedded(panel_class):
            def fill(self, plan: Any) -> None:
                self.table.setSortingEnabled(False)
                panel_class.fill(self, plan)
                for row in range(int(value(self.table, 'rowCount'))):
                    label = str(value(self.table.item(row, 0), 'text'))
                    for glyph in self.glyphs:
                        for master in self.chosen_masters():
                            if label == f'{glyph.name} · {master}':
                                layer = glyph.findLayer(master)
                                key = (glyph.name, master, getattr(layer, 'id', id(layer)))
                                self.table.item(row, 0).setData(QtCore.Qt.UserRole, key)
                self.table.setSortingEnabled(True)

            def apply(self) -> None:
                try:
                    owner.apply()
                except (ValueError, RuntimeError, TimeoutError) as error:
                    owner.studio.shell.set_status(str(error))

        self.panel_class = panel_class
        self.panel = fontui._construct(Embedded, self.widget)
        self.panel.setWindowFlags(QtCore.Qt.Widget)
        self.panel.setMinimumWidth(0)
        self.layout.addWidget(self.panel)
        for button in (self.panel.apply_button, self.panel.close_button, self.panel.reload_button):
            button.hide()
            button.setEnabled(False)
        table = self.panel.table
        table.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        table.horizontalHeader().setSectionResizeMode(QtGui.QHeaderView.Interactive)
        table.setSortingEnabled(False)
        self.connect(table.itemSelectionChanged, self.row_chosen)
        discard = QtGui.QPushButton('Discard preview', self.widget)
        self.connect(discard.clicked, lambda *args: self.discard())
        self.layout.addWidget(discard)
        studio.shell.set_actions(self, refresh=self.refresh, preview=self.preview,
            apply=self.apply, ready=self.ready, dirty=lambda: self.accepted is not None)

    def signature(self) -> tuple:
        package, glyphs = self.panel.live_glyphs()
        if package is not self.studio.package():
            raise ValueError('The captured font changed; reopen the studio.')
        chosen = list(self.panel.chosen_masters())
        masters = list(dict.fromkeys([*chosen, *self.panel.masters]))
        fields = []
        for kind, getter in ((QtGui.QDoubleSpinBox, 'value'), (QtGui.QSpinBox, 'value'),
                             (QtGui.QComboBox, 'currentIndex'), (QtGui.QCheckBox, 'isChecked')):
            fields.extend(value(control, getter) for control in self.panel.findChildren(kind))
        layers = []
        for glyph in glyphs:
            for master in masters:
                layer = glyph.findLayer(master)
                if layer is None or getattr(layer, 'isNull', False):
                    layers.append((glyph.name, master, None))
                    continue
                raw = tuple((getattr(shape.shapeData, 'note', ''), tuple(
                    tuple((getattr(n, 'nodeState', None), getattr(n, 'name', '')) for n in contour.nodes())
                    for contour in shape.contours)) for shape in layer.shapes)
                layers.append((glyph.name, master, getattr(glyph, 'id', id(glyph)),
                    getattr(layer, 'id', id(layer)), bool(layer.autoLayer), snapshot(layer), raw))
        return (tuple(chosen), tuple(fields), self.panel.options(), tuple(layers))

    def preview(self) -> None:
        self.accepted = None
        before = self.signature()
        self.panel.table.setSortingEnabled(False)
        self.panel.slot_error = ''
        self.panel.refresh()
        self.panel.table.setSortingEnabled(True)
        self.studio.shell.set_status(str(value(self.panel.status, 'text')))
        if self.panel.slot_error:
            raise ValueError(self.panel.slot_error)
        if self.panel.glyphs and before[0] and self.studio.preview is not None:
            self.studio.preview.load(self.panel.glyphs[0].name, before[0][0])
        if before != self.signature():
            raise ValueError('Source changed during preview; preview again.')
        if bool(value(self.panel.apply_button, 'isEnabled')):
            self.accepted = before

    def ready(self) -> bool:
        return self.accepted is not None and self.signature() == self.accepted

    def apply(self) -> None:
        if not self.ready():
            raise ValueError('Preview Changes first; target or controls changed.')
        self.accepted = None
        self.panel.table.setSortingEnabled(False)
        self.panel_class.apply(self.panel)
        self.studio.shell.set_status(str(value(self.panel.status, 'text')))
        if self.studio.preview is not None:
            self.studio.preview.refresh()

    def refresh(self) -> None:
        self.studio.package()
        self.panel.reload()
        self.accepted = None

    def discard(self) -> None:
        self.accepted = None
        self.studio.shell.set_status('Preview discarded; font unchanged by discard.')

    def row_chosen(self) -> None:
        try:
            items = self.panel.table.selectedItems()
            if not items or self.studio.preview is None:
                return
            key = self.panel.table.item(int(value(items[0], 'row')), 0).data(QtCore.Qt.UserRole)
            if key is not None:
                name, master, identity = key
                layer = self.studio.layer(name, master)
                if getattr(layer, 'id', id(layer)) != identity:
                    raise ValueError('The captured layer changed; preview again.')
                self.studio.preview.load(name, master)
        except (ValueError, RuntimeError) as error:
            self.studio.shell.set_status(str(error))

    def close(self) -> None:
        self.closed = True
        if not getattr(self, '_panel_closed', False) and hasattr(self, 'panel'):
            if self.panel.close() is False:
                raise RuntimeError('Outline tab refused Close; retry Close.')
            self._panel_closed = True
        super().close()


def show(title: str, parent: Any = None, *, package: Any = None, font: Any = None,
         preview: Any = None, panels: Any = None) -> Any:
    """Open exact original tasks in one owned shell and read-only TGlyph preview."""
    specs = PANELS[title]
    shell = fontui.app_shell(title, 'tglyph', parent=parent, package=package)
    try:
        studio = Studio(shell, font=capture(shell, font))
        studio.APP = title
        studio.reload()
        studio.preview = (preview(shell, studio) if preview else fontui.glyph_view(
            studio.font(), shell.widget, layer=studio.master, controls=False, read_only=True))
        if studio.preview is not None:
            shell.set_preview(studio.preview)
        for label, module, cls in specs:
            panel_class = (panels[label] if panels is not None else getattr(importlib.import_module(
                'fontlabapp.fontui.' + ('outline_routes.' + module if module else 'superaligner')), cls))
            task = fontui._construct(OutlineTask, studio, panel_class)
            shell.add_tab(TabSpec(label, lambda owner, task=task: task))
        if title == 'Transform Studio':
            shell.add_tab(TabSpec('Raise Ascender', lambda owner: fontui.raise_ascender_tab(studio)))
        shell.set_about(title + '\nPreview Changes before Apply Changes. Original selected-layer and Undo scopes are retained.\n'
            'Sources: github.com/fontlabcom/fontlab-python-scriptmix; github.com/simoncozens/GlyphsScripts.\n'
            'FontLab contributors (Apache-2.0), independent adaptations after Simon Cozens (MIT). See NOTICE.')
        shell.show()
    except BaseException as error:
        _cleanup_failure(shell, error)
        raise
    return shell
