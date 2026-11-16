# this_file: tests/test_wp05_outline_editing.py
"""Named Outline Doctor/Curve Editor tabs retain guards and accepted plans."""
import importlib
import sys
from types import SimpleNamespace as NS

import pytest
from _outline_fakes import T
from _studio_qt import studio_qt  # noqa: F401
from test_studio_outline_doctor import font, same_small
from test_studio_outline_doctor import qt_doctor as _qt_doctor

qt_doctor = _qt_doctor


@pytest.fixture
def editor(qt_doctor, monkeypatch):
    monkeypatch.delitem(sys.modules, 'fontlabapp.fontui.outline_editing', raising=False)
    module = importlib.import_module('fontlabapp.fontui.outline_editing')
    pkg = font(A=same_small)
    for master in pkg.masters:
        object.__setattr__(pkg.layer('A', master), 'advanceWidth', 600)
        for shape in pkg.layer('A', master).shapes:
            shape.transform = T()
    preview = qt_doctor.modules.lifecycle.Owned(None)
    preview.load = lambda *a: None
    preview.set_overlay = lambda *a: None
    preview.highlight = lambda **kw: None
    preview.refresh = lambda: None
    shell = module.show('Outline Doctor', package=lambda: pkg, font=lambda: object(), preview=lambda *a: preview)
    qt_doctor.owned.append(shell)
    return NS(module=module, shell=shell, pkg=pkg)


def test_named_routes_and_preview_apply_guard(editor):
    assert len(editor.shell.operation_tabs) == 9
    tab = editor.shell.operation_tabs[0]
    tab.glyphs_field.setText('A')
    with pytest.raises(ValueError, match='Preview'):
        tab.apply_changes()
    tab.preview_changes()
    assert tab.ready()
    editor.pkg.layer('A', 'Regular').shapes[0].contours[0].nodes()[0].x += 1
    assert not tab.ready()
    with pytest.raises(ValueError, match='changed'):
        tab.apply_changes()


def test_preview_keeps_staged_plan_until_discard(editor):
    tab = editor.shell.operation_tabs[0]
    tab.glyphs_field.setText('A')
    tab.preview_changes()
    editor.shell._run_action('refresh')
    assert 'discard staged' in editor.shell.status.text()
    tab.discard()
    assert not tab.ready()
    assert editor.pkg.writes() == []


def test_curve_editor_has_five_exact_routes_and_rejects_unknown(editor, qt_doctor):
    with pytest.raises(ValueError):
        editor.module.show('Unknown')
    shell = editor.module.show('Curve Editor', package=lambda: editor.pkg,
                              font=lambda: object(), preview=lambda *a: None)
    qt_doctor.owned.append(shell)
    assert [tab.check().title for tab in shell.operation_tabs] == [
        'Curve All Straights', 'Straighten All Curves', 'Straighten Short Curves',
        'Retract Handles', 'Simplify Selected Nodes']


def test_apply_original_fix_and_reject_locked_shape(editor, monkeypatch):
    tab = editor.shell.operation_tabs[4]  # Delete Small Contours
    tab.glyphs_field.setText('A')
    calls = []
    def history(label, glyphs, mutate, **kw):
        calls.append(label)
        mutate()
        return NS(mismatches=kw['read_back']())
    monkeypatch.setattr(editor.shell, 'history', history)
    tab.preview_changes()
    assert tab.apply_changes() is True
    assert calls and not tab.ready()
    target = editor.pkg.layer('A', 'Regular')
    target.shapes[0].contentLocked = True
    with pytest.raises(ValueError, match='Unlock'):
        tab.preview_changes()


def test_legacy_adapter_keeps_edits_and_reports_advice(editor):
    from fontlabapp.contours.writer import Change
    calls = []
    legacy = NS(prepare=lambda layer, edits: calls.append(('prepare', edits)) or edits,
                write=lambda layer, edits: calls.append(('write', edits)),
                check=lambda rows: ['mismatch'], advice=['save risk'])
    check = editor.module.native_check('x', 'Example', lambda layer, values, context: [Change('n','old','new',42)], legacy)
    rows = check.plan('layer', {}, None)
    assert rows[0].edit == 42
    check.write('layer', [42], {})
    assert calls == [('prepare', [42]), ('write', [42])]
    assert check.verify('layer', [42]) == ['mismatch']
    assert check.advise('layer', [42]) == ['save risk']


def test_during_preview_mutation_invalidates_acceptance(editor, monkeypatch):
    tab = editor.shell.operation_tabs[0]
    tab.glyphs_field.setText('A')
    target = editor.pkg.layer('A', 'Regular')
    monkeypatch.setattr(tab, 'preview_fix', lambda: setattr(target, 'advanceWidth', 601))
    with pytest.raises(ValueError, match='during preview'):
        tab.preview_changes()
    assert not tab.ready()


def test_missing_target_is_recorded_and_default_preview_read_only(editor, monkeypatch):
    tab = editor.shell.operation_tabs[0]
    tab.glyphs_field.setText('A')
    monkeypatch.setattr(tab.studio, 'layer', lambda *args: None)
    assert ('A', 'Regular', None) in tab.signature()[-1]
    calls = []
    monkeypatch.setattr(editor.module.fontui, 'glyph_view', lambda *a, **kw: calls.append(kw))
    editor.module._preview(editor.shell, editor.shell.outline_doctor)
    assert calls[0]['read_only'] is True and calls[0]['controls'] is False
    with pytest.raises(ValueError, match='Open a font'):
        editor.module.show(package=lambda: None, font=lambda: None)


def test_hidden_hint_action_and_changed_font_refuse(editor, monkeypatch):
    tab = editor.shell.operation_tabs[0]
    assert tab.remove_hints() == 0
    for button in tab.widget.findChildren(editor.module.QtGui.QPushButton):
        if button.text() == 'Remove PostScript hints':
            assert button.isHidden() and not button.isEnabled()
    monkeypatch.setattr(tab.studio, '_selection', lambda: ['A'])
    assert tab.use_selection() == ['A']
    monkeypatch.setattr(editor.shell, '_package', lambda: (_ for _ in ()).throw(ValueError('active font changed')))
    assert tab.use_selection() == []
    tab.row_chosen('A', 'Regular')
    assert 'Preview unavailable' in editor.shell.status.text()


def test_source_raw_flags_and_notes_are_part_of_acceptance(editor):
    tab = editor.shell.operation_tabs[0]
    tab.glyphs_field.setText('A')
    tab.preview_changes()
    shape = editor.pkg.layer('A', 'Regular').shapes[0]
    shape.note = 'changed after preview'
    assert not tab.ready()
    tab.preview_changes()
    shape.contours[0].nodes()[0].nodeState = 0x8000
    assert not tab.ready()


def test_prepared_payload_replaces_input_and_wrong_count_refuses(editor):
    from fontlabapp.contours.writer import Change
    strategy = NS(prepare=lambda layer, edits: [(42, 'prepared')],
                  write=lambda *args: None, check=lambda rows: [])
    operation = editor.module.native_check('x', 'X', lambda *a: [Change('n','','',42)], strategy)
    assert operation.plan(None, {}, None)[0].edit == (42, 'prepared')
    strategy.prepare = lambda layer, edits: []
    with pytest.raises(ValueError, match='no longer match'):
        operation.plan(None, {}, None)


@pytest.mark.parametrize('key,function', [
    ('add_extremes','extreme_changes'), ('delete_close_points','changes'),
    ('delete_duplicate_contours','duplicate_changes'), ('delete_small_contours','small_changes'),
    ('fix_zero_handles','zero_changes'), ('remove_overlap','overlap_changes'),
    ('round_coordinates','round_changes'), ('straighten_short_curves','straighten_changes'),
    ('retract_handles','changes'), ('curve_all_straights','changes'), ('straighten_all_curves','changes')])
def test_named_tabs_call_same_migrated_original_strategy(editor, monkeypatch, key, function):
    route = importlib.import_module('fontlabapp.fontui.outline_routes.' + key)
    calls = []
    monkeypatch.setattr(route, function, lambda *args: calls.append(args) or [])
    monkeypatch.setattr(editor.module.layer_selection, 'capture', lambda deadline: NS(occurrences=(NS(glyph_name='A', layer='reference'),)))
    title = 'Outline Doctor' if key in editor.module.OUTLINE else 'Curve Editor'
    operation = next(c for c in editor.module.checks(title) if c.key == key)
    assert operation.plan('layer', operation.defaults(), NS(glyph='A', reference='reference')) == []
    assert calls[0][0] == 'layer'


def test_conversion_missing_selection_is_note_and_source_context_is_reviewed(editor, monkeypatch, qt_doctor):
    capture = NS(occurrences=())
    monkeypatch.setattr(editor.module.layer_selection, 'capture', lambda deadline: capture)
    route = importlib.import_module('fontlabapp.fontui.outline_routes.curve_all_straights')
    assert editor.module._conversion(route, None, NS(glyph='A'))[0].edit is None
    shell = editor.module.show('Curve Editor', package=lambda: editor.pkg,
                              font=lambda: object(), preview=lambda *a: None)
    qt_doctor.owned.append(shell)
    tab = shell.operation_tabs[0]
    tab.glyphs_field.setText('A')
    tab.preview_changes()
    tab.discard()
    assert tab.signature()[-2][0] is capture


def test_straighten_route_rejects_quadratic_and_malformed_spans(editor):
    from _outline_fakes import OContour

    route = importlib.import_module('fontlabapp.fontui.outline_routes.straighten_all_curves')
    with pytest.raises(ValueError, match='closed PostScript'):
        route.spans(OContour([(0,0,True)], tt=True))
    with pytest.raises(ValueError, match='unsupported segment'):
        route.spans(OContour([(0,0,True), (1,1,False), (2,0,True)]))
    with pytest.raises(RuntimeError, match='refused segment conversion'):
        route.ConversionEditor().write(None, [(None, [NS(convertToLine=lambda: False)], 0)])


def test_straighten_route_keeps_mismatched_types_and_missing_selected_glyph(editor, monkeypatch):
    from _outline_fakes import OContour, OShape

    route = importlib.import_module('fontlabapp.fontui.outline_routes.straighten_all_curves')
    reference = NS(shapes=[OShape([OContour([(0,0,True),(1,1,True),(2,0,True)])], transform=T())])
    target = NS(shapes=[OShape([OContour([(0,0,True),(1,1,False),(2,0,True)])], transform=T())])
    assert 'incompatible point types' in route.changes(target, reference)[0].new
    monkeypatch.setattr(route.layer_selection, 'capture', lambda deadline: NS(occurrences=()))
    planner = route.ToolPanel.planner(NS())
    assert 'no current selected layer' in planner(NS(name='A'), 'Regular', target)[0].new
