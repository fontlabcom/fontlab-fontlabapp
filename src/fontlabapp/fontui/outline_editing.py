# this_file: src/fontlabapp/fontui/outline_editing.py
# SPDX-License-Identifier: Apache-2.0
"""Named outline/curve task tabs over the existing Doctor and native strategies."""
from importlib import import_module
from time import monotonic
from typing import Any

from PythonQt import QtGui

import fontlabapp.fontui as fontui  # noqa: PLR0402 - native package lookup
from fontlabapp.core.scripting import current_package
from fontlabapp.masters.layers import selection as layer_selection
from fontlabapp.qt.widgets import _cleanup_failure
from fontlabapp.studios import TabSpec
from fontlabapp.studios.outline_doctor.checks import by_key
from fontlabapp.studios.outline_doctor.model import Check, Issue, Option
from fontlabapp.studios.outline_doctor.session import Doctor
from fontlabapp.studios.outline_doctor.tabs import FixTab
from fontlabapp.studios.transform_studio.native import snapshot
from fontlabapp.studios.transform_studio.tabs import _button, _check

from . import outline_order as order
from . import outline_simplify as simplify

OUTLINE = ('add_extremes', 'correct_direction', 'delete_close_points',
           'delete_duplicate_contours', 'delete_small_contours', 'fix_zero_handles',
           'optimize_start_points', 'remove_overlap', 'round_coordinates')
CURVES = ('curve_all_straights', 'straighten_all_curves', 'straighten_short_curves',
          'retract_handles', 'simplify_selected_nodes')


def native_check(key: str, title: str, planner: Any, editor: Any, *, structural: bool = False,
            options: tuple = ()) -> Check:
    """Adapt existing plans without changing their edits, compatibility keys or advice."""
    def plan(layer: Any, values: dict, context: Any) -> list[Issue]:
        changes = planner(layer, values, context)
        edits = [row.edit for row in changes if row.edit is not None]
        prepared = editor.prepare(layer, edits)
        if len(prepared) != len(edits):
            raise ValueError('Prepared outline edits no longer match the preview rows.')
        prepared = iter(prepared)
        return [Issue(row.name, row.old, row.new, next(prepared) if row.edit is not None else None,
                      row.problem, row.key) for row in changes]

    return Check(key, title, title, title.lower(), title + '.py', plan,
                 lambda layer, edits, values: editor.write(layer, edits),
                 lambda layer, edits: editor.check([(layer, edits)]),
                 structural=structural, scope='all', options=options, bases=True,
                 advise=lambda layer, edits: getattr(editor, 'advice', ()))


def checks(title: str) -> tuple[Check, ...]:
    if title not in ('Outline Doctor', 'Curve Editor'):
        raise ValueError('Choose Outline Doctor or Curve Editor.')
    extra = {
        'correct_direction': native_check('correct_direction', 'Correct Contour Direction',
            lambda layer, values, context: order.direction_changes(layer), order.ReverseEditor()),
        'optimize_start_points': native_check('optimize_start_points', 'Optimize Start Points',
            lambda layer, values, context: order.start_changes(layer, context.reference if values['match'] else None),
            order.StartEditor(), structural=True,
            options=(Option('match', 'Match current master (keeps masters compatible)', 'tick', True),)),
        'simplify_selected_nodes': native_check('simplify_selected_nodes', 'Simplify Selected Nodes',
            lambda layer, values, context: simplify.changes(layer, context.reference),
            simplify.SimplifyEditor(), structural=True),
    }
    def migrated(key: str) -> Check:
        if key in extra:
            return extra[key]
        base = by_key(key)
        module = import_module('fontlabapp.fontui.outline_routes.' + key)
        strategies = {
            'add_extremes': (lambda layer, values, context: module.extreme_changes(layer), 'ExtremesEditor'),
            'delete_close_points': (lambda layer, values, context: module.changes(layer, values['distance']), 'MergeEditor'),
            'delete_duplicate_contours': (lambda layer, values, context: module.duplicate_changes(layer, values['tolerance']), 'RemoveEditor'),
            'delete_small_contours': (lambda layer, values, context: module.small_changes(layer, values['threshold']), 'RemoveEditor'),
            'fix_zero_handles': (lambda layer, values, context: module.zero_changes(layer, values['pull']), 'HandleEditor'),
            'remove_overlap': (lambda layer, values, context: module.overlap_changes(layer, {}), 'MergeEditor'),
            'round_coordinates': (lambda layer, values, context: module.round_changes(layer, int(values['grid']), values['offsets'], values['anchors']), 'RoundEditor'),
            'straighten_short_curves': (lambda layer, values, context: module.straighten_changes(layer, values['chord'], values['handles']), 'LineEditor'),
            'retract_handles': (lambda layer, values, context: module.changes(layer, values['selected'], context.reference), 'RetractEditor'),
            'curve_all_straights': (lambda layer, values, context: _conversion(module, layer, context), 'ConversionEditor'),
            'straighten_all_curves': (lambda layer, values, context: _conversion(module, layer, context), 'ConversionEditor'),
        }
        planner, editor = strategies[key]
        return native_check(key, base.title, planner, getattr(module, editor)(),
                            structural=base.structural, options=base.options)._replace(scope=base.scope)
    return tuple(migrated(key) for key in (OUTLINE if title == 'Outline Doctor' else CURVES))


def _conversion(module: Any, layer: Any, context: Any) -> list:
    selected = layer_selection.capture(monotonic() + 2)
    reference = next((o.layer for o in selected.occurrences if o.glyph_name == context.glyph), None)
    if reference is None:
        return [module.writer.Change('glyph', '', 'no current selected layer, kept')]
    return module.changes(layer, reference)



class OperationTab(FixTab):
    """One stable task identity with a reviewed source snapshot and original options."""

    def __init__(self, studio: Doctor, check: Check):
        self.operation, self.accepted = check, None
        super().__init__(studio)
        for button in self.widget.findChildren(QtGui.QPushButton):
            label = button.text() if callable(button.text) else button.text
            if label == 'Remove PostScript hints':
                button.setEnabled(False)
                button.hide()
        studio.shell.set_actions(self.widget, refresh=studio.reload, preview=self.preview_changes,
                                 apply=self.apply_changes, ready=self.ready,
                                 dirty=lambda: self.accepted is not None)

    def use_selection(self) -> list[str]:
        try:
            self.studio.package()
            return super().use_selection()
        except Exception as error:  # noqa: BLE001 - contain native Qt callback failures
            self.studio.say(str(error))
            return []

    def row_chosen(self, name: str, layer: Any = None) -> None:
        try:
            self.studio.package()
            super().row_chosen(name, layer)
        except Exception as error:  # noqa: BLE001 - contain native Qt callback failures
            self.studio.say(f"Preview unavailable: {error}")

    def remove_hints(self) -> int:
        self.studio.say('Use Hint Tools to remove PostScript hints.')
        return 0

    def check(self) -> Check:
        return self.operation

    def controls(self) -> None:
        check = self.check()
        self.compatible = _check(self.widget, self.line(), 'Keep masters compatible', True)
        self.compatible.setVisible(check.structural)
        self.inputs = {check.key: {option.key: self.option(self.line(), option) for option in check.options}}
        self.all_masters.setChecked(check.scope == 'all')
        self.allow_bases.setVisible(check.bases)
        _button(self.widget, self.line(), 'Discard Preview', self.discard)

    def discard(self) -> None:
        self.accepted = None
        self.show_rows([])
        if self.studio.preview is not None:
            self.studio.preview.set_overlay(None)

    def signature(self) -> tuple:
        """Read all masters used by compatibility checks; hold locked shapes/layers."""
        studio = self.studio
        studio.package()
        facts = []
        for name in self.names():
            for master in studio.masters:
                layer = studio.layer(name, master)
                if layer is None:
                    facts.append((name, master, None))
                    continue
                if layer.isLocked or any(shape.contentLocked for shape in layer.shapes):
                    raise ValueError('Unlock the target layer and shapes before previewing changes.')
                facts.append((name, master, getattr(layer, 'id', id(layer)), snapshot(layer),
                              bool(layer.autoLayer), tuple(
                                  (getattr(shape, 'note', ''), tuple(
                                      tuple(getattr(node, 'nodeState', None) for node in contour.nodes())
                                      for contour in shape.contours))
                                  for shape in layer.shapes)))
        selected = None
        if self.check().key in ('curve_all_straights', 'straighten_all_curves'):
            source = layer_selection.capture(monotonic() + 2)
            selected = (source, tuple(snapshot(o.layer) for o in source.occurrences))
        return (tuple(self.names()), studio.master, self.options(), self._kwargs(), selected, tuple(facts))

    def preview_changes(self) -> list:
        self.accepted = None
        before = self.signature()
        rows = self.preview_fix()
        if before != self.signature():
            raise ValueError('Source changed during preview; refresh and preview again.')
        self.accepted = before
        return rows

    def ready(self) -> bool:
        return self.accepted is not None and self.accepted == self.signature()

    def apply_changes(self) -> bool:
        if not self.ready():
            raise ValueError('Preview Changes first; inputs or source changed.')
        try:
            return self.apply_fix()
        finally:
            self.accepted = None


def show(title: str = 'Outline Doctor', parent: Any = None, *, package: Any = None,
         font: Any = None, preview: Any = None) -> Any:
    """Open one captured font; preserve per-task staged plans when switching tabs."""
    operations = checks(title)
    shell = fontui.app_shell(title, 'tglyph', parent=parent, package=package)
    try:
        captured_package = shell.package()
        captured_font = (font or fontui.current_font)()
        if captured_package is None or captured_font is None:
            raise ValueError('Open a font first.')
        supplier = package or current_package
        def bound_package() -> Any:
            current = supplier()
            if current is None or getattr(current, 'id', id(current)) != getattr(captured_package, 'id', id(captured_package)):
                raise ValueError('Active font changed; reopen the outline tool for that font.')
            return captured_package
        shell._package = bound_package
        studio = shell.outline_doctor = Doctor(shell, font=lambda: captured_font)
        studio.APP = title
        studio.reload()
        studio.preview = (preview or _preview)(shell, studio)
        if studio.preview is not None:
            shell.set_preview(studio.preview)
        shell.operation_tabs = []
        for check in operations:
            tab = OperationTab(studio, check)
            shell.add_tab(TabSpec(check.title, lambda owner, tab=tab: tab.widget))
            shell.operation_tabs.append(tab)
        studio.reload()
        shell.set_about(
            title + '\nPreview each task before Apply Changes. Discard Preview before Refresh.\n'
            'Geometry changes use the original guarded native strategies and one history step.\n'
            'FontLab App contributors (Apache-2.0); independent adaptations after Simon Cozens '
            '(MIT) and Pedro Arilla (Apache-2.0).\n'
            'Sources: github.com/fontlabcom/fontlab-python-scriptmix, '
            'github.com/simoncozens/GlyphsScripts, github.com/pedroarilla/glyphs-scripts.\n'
            'See Scriptmix NOTICE for exact provenance and licence notices.'
        )
        shell.show()
    except BaseException as error:
        _cleanup_failure(shell, error)
        raise
    return shell


def _preview(shell: Any, studio: Doctor) -> Any:
    return fontui.glyph_view(studio.font(), shell.widget, layer=studio.current,
                             controls=False, read_only=True, label_prefix=studio.APP,
                             hint_check=shell.hint_check)
