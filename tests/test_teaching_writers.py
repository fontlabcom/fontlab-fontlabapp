# this_file: tests/test_teaching_writers.py
"""The teaching writer routes retain the existing guarded algorithms."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / 'src/fontlabapp/fontui/teaching_writers'


@pytest.mark.parametrize('module,function', [
    ('node_table', 'apply_edits'),
    ('node_slope_and_handles', 'changes'),
    ('stem_blend', 'prepare_blend'),
    ('scale_with_stem_compensation', 'make_plan'),
    ('kerning_copy_rules', 'expand_rules'),
    ('import_kerning_pair_list', 'parse_pairs'),
    ('font_info_snapshot', 'snapshot_json'),
    ('font_name_encoding_audit', 'encoding_report'),
    ('localized_font_names', 'name_feature'),
    ('copy_layers_from_font', 'apply_plan'),
    ('layer_metric_comparison', 'build_output'),
])
def test_writer_route_preserves_callable(module, function):
    spec = importlib.util.spec_from_file_location(module, ROOT / f'{module}.py')
    implementation = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(implementation)
    assert callable(getattr(implementation, function))

from _studio_qt import studio_qt  # noqa: F401,E402


def test_metadata_lab_keeps_three_real_panels_and_refuses_unsaved_refresh(studio_qt, monkeypatch):  # noqa: F811 - shared Qt fixture
    import importlib
    import sys
    from types import SimpleNamespace as NS

    monkeypatch.delitem(sys.modules, 'fontlabapp.fontui.teaching.host', raising=False)
    app = importlib.import_module('fontlabapp.fontui.teaching_writers.app')
    for name in ('font_info_snapshot', 'font_name_encoding_audit', 'localized_font_names'):
        module = importlib.import_module('fontlabapp.fontui.teaching_writers.' + name)
        monkeypatch.setattr(module, 'capture_info', lambda module=module: ('Regular', {
            **{field: '' for field in module.FIELDS},
            'familyName': 'Test', 'styleName': 'Regular',
            'openTypeNamePreferredFamilyName': '',
            'openTypeNamePreferredSubfamilyName': '',
        }))
    shell = app.show('Font Metadata Lab')
    panels = [child.panel for child in shell.children]
    assert shell.tabs.count() == 4
    assert all(not panel.isWindow() for panel in panels)
    assert panels[0].preview.toPlainText()
    shell.tabs.setCurrentIndex(2)
    panels[2].family_field.setText('Edited')
    shell._run_action('refresh')
    assert 'discard staged edits' in shell.status.text()
    with pytest.raises(RuntimeError, match='refused'):
        shell.close()
    assert shell.children[-1].panel is panels[2]
    panels[2].unsaved = False
    shell.close()
    assert app.ready(NS(plan_data=None)) is False
    assert app.ready(NS(plan_data={})) is True
    assert app.ready(NS(snapshot_data=None)) is False
    assert app.ready(NS(snapshot_data=object())) is True
    button = studio_qt.modules.appshell.QtGui.QPushButton()
    assert app.ready(NS(apply_button=button)) is True
    button.setEnabled(False)
    assert app.ready(NS(apply_button=button)) is False


def test_node_table_sorted_cells_keep_identity_and_dirty_refresh(studio_qt, monkeypatch):  # noqa: F811 - shared Qt fixture
    import importlib
    import sys
    from types import SimpleNamespace as NS

    module = importlib.import_module('fontlabapp.fontui.teaching_writers.node_table')
    assembly = importlib.import_module('fontlabapp.fontui.teaching_writers.app')
    qt = sys.modules['PythonQt']
    rows = tuple(module.NodeRow((0, 0, index), x, 0.0, 'line', '', False, object())
                 for index, x in enumerate((10.0, 2.0)))
    snapshot = NS(rows=rows, context=(1, 2, 3, 4), facts=object())
    monkeypatch.setattr(module, 'capture_nodes', lambda **kwargs: snapshot)
    selections, writes = [], []
    monkeypatch.setattr(module, 'select_nodes', lambda snapshot, keys: selections.append(keys) or {})
    monkeypatch.setattr(module, 'apply_edits', lambda snapshot, cells: writes.append(cells) or NS(
        changed=1, kept={}, facts=snapshot.facts, pending_note=''))
    panel = module.show(qt, None, embedded=True)
    refreshed = []
    panel.lab_refresh_preview = lambda: refreshed.append(True)
    panel.refresh_nodes()
    assert refreshed == [True]
    assert panel.node_table.isSortingEnabled()
    panel.node_table.sortItems(3, qt.QtCore.Qt.AscendingOrder)
    assert panel.rows_in_view()[0].key == (0, 0, 1)
    panel.node_table.selectRow(0)
    assert selections[-1] == {(0, 0, 1)}
    assert not panel.staged_edits()
    panel.node_table.item(0, 3).setText('22')
    assert panel.staged_edits() and assembly.dirty(panel)
    panel.write_cells()
    assert writes[-1][(0, 0, 1)][0] == '22'
    assert writes[-1][(0, 0, 0)][0] == '10'
    assert not panel.staged_edits()
    panel.node_table.item(0, 3).setText('invalid')
    assert panel.staged_edits()
    panel.close()


@pytest.mark.parametrize('name', ['font_info_snapshot', 'font_name_encoding_audit', 'localized_font_names'])
def test_metadata_capture_rejects_nontext_fields_and_missing_master(name, monkeypatch):
    import importlib
    import sys
    from types import SimpleNamespace as NS

    module = importlib.import_module('fontlabapp.fontui.teaching_writers.' + name)
    package = NS(id=1, isNull=False, master='Regular', info=NS(**dict.fromkeys(module.FIELDS, '')))
    native = NS(flWorkspace=NS(instance=lambda: NS(currentPackage=package)))
    monkeypatch.setitem(sys.modules, 'fontlab', native)
    assert module.capture_info()[0] == 'Regular'
    package.master = ''
    with pytest.raises(ValueError, match='master'):
        module.capture_info(native)
    package.master = 'Regular'
    package.info.familyName = 12
    with pytest.raises(ValueError, match='text'):
        module.capture_info(native)


def test_recipe_boundaries_refuse_ambiguous_collision_and_nonintegral_kerning():
    from fontlabapp.fontui.teaching_writers import copy_layers_from_font as layers
    from fontlabapp.fontui.teaching_writers import kerning_copy_rules as kerning

    with pytest.raises(ValueError, match='collision mode'):
        layers.collision('Regular', '', 'Unknown', True)
    with pytest.raises(ValueError, match='suffix'):
        layers.collision('Regular', '', 'Incoming + suffix', False)
    assert kerning.expand_rules('# comment\n\nA|V = T|o', {('T', 'o'): 0}) == {('A', 'V'): 0}
    for value in (float('nan'), 0.5):
        with pytest.raises(ValueError, match='whole units'):
            kerning.expand_rules('A|V = T|o', {('T', 'o'): value})
    with pytest.raises(ValueError, match='destination'):
        kerning.expand_rules(' = T|o', {('T', 'o'): 0})


def test_metric_boundary_refuses_expired_scan_and_tsv_names(monkeypatch):
    from types import SimpleNamespace as NS
    from fontlabapp.fontui.teaching_writers import layer_metric_comparison as metrics

    selected = NS(occurrences=[NS(glyph_name='A', layer_name='Regular')])
    with pytest.raises(TimeoutError):
        metrics.read_rows(selected, 0)
    selected.occurrences[0].glyph_name = 'A\tB'
    with pytest.raises(ValueError, match='TSV'):
        metrics.read_rows(selected, float('inf'))
    monkeypatch.setattr(metrics, 'current_thread', lambda: object())
    with pytest.raises(RuntimeError, match='main UI thread'):
        metrics.capture_metrics()


def test_node_capture_refuses_missing_and_mismatched_context(monkeypatch):
    import sys
    from types import SimpleNamespace as NS
    from fontlabapp.fontui.teaching_writers import node_table as nodes

    package = NS(id=1, fgId=2, isNull=False)
    font = NS(id=2)
    native = NS(flWorkspace=NS(instance=lambda: NS(currentPackage=package)),
                CurrentGlyph=lambda: NS(id=3), CurrentFont=lambda: font)
    monkeypatch.setitem(sys.modules, 'fontlab', native)
    assert nodes.native_module() is native
    monkeypatch.setattr(nodes, 'current_thread', lambda: object())
    with pytest.raises(RuntimeError, match='main UI thread'):
        nodes.native_module(native)
    monkeypatch.undo()
    package.isNull = True
    with pytest.raises(ValueError, match='Open a font'):
        nodes.current_context(native)
    package.isNull = False
    font.id = 5
    with pytest.raises(ValueError, match='font changed'):
        nodes.current_context(native)
    font.id = 2
    package.findFgId = lambda id: None
    with pytest.raises(ValueError, match='another font'):
        nodes.current_context(native)
    package.findFgId = lambda id: NS(isNull=False, package=package, activeLayer=None)
    with pytest.raises(ValueError, match='active layer'):
        nodes.current_context(native)


def test_writer_lab_factory_preserves_actions_and_cleans_failed_preview(studio_qt, monkeypatch):  # noqa: F811 - shared Qt fixture
    import importlib
    import sys
    from types import SimpleNamespace as NS

    monkeypatch.delitem(sys.modules, 'fontlabapp.fontui.teaching.host', raising=False)
    host = importlib.import_module('fontlabapp.fontui.teaching.host')
    app = importlib.import_module('fontlabapp.fontui.teaching_writers.app')
    gui = studio_qt.modules.appshell.QtGui
    actions = []

    class Panel(gui.QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.close_button = gui.QPushButton(self)
            self.plan_data = None
            self.mapping_table = gui.QTableWidget(self)
            self.master_table = gui.QTableWidget(2, 6, self)
            for row, number in enumerate((100, 50)):
                for column in (4, 5):
                    self.master_table.setItem(row, column, gui.QTableWidgetItem(str(number)))
        def reload_selection(self):
            actions.append('reload')
            self.lab_refresh_preview()
        def preview_copy(self):
            self.plan_data = {'target': 1}
        def copy_rows(self):
            self.lab_check_target()
            actions.append('write')
        def refresh_output(self):
            actions.append('metrics')

    monkeypatch.setattr(app, 'import_module', lambda name: NS(panel_type=lambda: Panel))
    monkeypatch.setattr(host, 'bind_current_preview', lambda shell: None)
    monkeypatch.setattr(host, 'refresh_current_preview', lambda shell: actions.append('preview refreshed'))
    monkeypatch.setattr(host, 'require_current_preview', lambda shell: actions.append('target checked'))
    shell = app.show('Layer Transfer Lab')
    assert [shell.tabs.tabText(i) for i in range(3)] == ['Layer copies', 'Metric comparison', 'About']
    panel = shell.children[0].panel
    assert panel.close_button.isHidden() and not panel.close_button.isEnabled()
    panel.master_table.sortItems(4)
    assert panel.master_table.item(0, 4).text() == '50' 
    shell._run_action('apply')
    assert not actions
    shell._run_action('refresh')
    assert actions == ['reload', 'preview refreshed']
    shell._run_action('preview')
    shell._run_action('apply')
    assert actions[-2:] == ['target checked', 'write']
    shell.close()
    monkeypatch.setattr(host, 'bind_current_preview', lambda shell: (_ for _ in ()).throw(ValueError('no preview')))
    with pytest.raises(ValueError, match='no preview'):
        app.show('Layer Transfer Lab')
    assert not host.OPEN


def test_layer_copy_refuses_unpreservable_source_content():
    from types import SimpleNamespace as NS
    from fontlabapp.fontui.teaching_writers import copy_layers_from_font as layers

    with pytest.raises(ValueError, match='missing'):
        layers.usable(None, source=True)
    layer = NS(isNull=False, autoLayer=True, isLocked=False, isService=False)
    with pytest.raises(ValueError, match='automatic'):
        layers.usable(layer, source=True)
    layer.autoLayer = False
    layer.hasHints, layer.hasTTH, layer.guidelines = True, False, []
    with pytest.raises(ValueError, match='hints'):
        layers.usable(layer, source=True)
    layer.hasHints = False
    layer.metricsLeft, layer.metricsRight, layer.metricsWidth = '=A', '', ''
    with pytest.raises(ValueError, match='expressions'):
        layers.usable(layer, source=True)
    layer.metricsLeft = ''
    layer.shapes = [NS(isComponent=True)]
    with pytest.raises(ValueError, match='components'):
        layers.usable(layer, source=True)


def test_stem_scale_refuses_extreme_slant_and_extrapolation():
    from fontlabapp.fontui.teaching_writers import scale_with_stem_compensation as scale

    with pytest.raises(ValueError, match='slant angle'):
        scale.blend_contours([], [], (50, 100, 50, 100), (75, 75), (1, 1), 85)
    with pytest.raises(ValueError, match='between source stems'):
        scale.blend_contours([], [], (50, 100, 50, 100), (150, 75), (1, 1), 0)
    with pytest.raises(ValueError, match='source layer'):
        scale.read_contours(None, 0)


def test_pair_import_sort_keeps_whole_plan_and_checks_preview_target(studio_qt, monkeypatch):  # noqa: F811 - shared Qt fixture
    import sys
    from fontlabapp.fontui.teaching_writers import import_kerning_pair_list as pairs

    plan = {'master': 'Regular', 'rows': [
        {'line': 10, 'left': 'V', 'right': 'A', 'current': None, 'value': -20, 'error': ''},
        {'line': 2, 'left': 'A', 'right': 'V', 'current': 0, 'value': -40, 'error': ''},
    ]}
    monkeypatch.setattr(pairs, 'prepare_pairs', lambda text: plan)
    written, refreshed = [], []
    monkeypatch.setattr(pairs, 'apply_pairs', lambda value, text: written.append(value) or True)
    panel = pairs.show(sys.modules['PythonQt'], None, embedded=True)
    panel.lab_refresh_preview = lambda: refreshed.append(True)
    panel.lab_check_target = lambda: (_ for _ in ()).throw(ValueError('Preview target changed'))
    panel.preview_pairs()
    assert refreshed == [True] and panel.preview_table.isSortingEnabled()
    panel.preview_table.sortItems(0)
    assert panel.preview_table.item(0, 0).text() == '2'
    panel.preview_table.sortItems(1)
    assert panel.preview_table.item(0, 1).text() == 'A'
    panel.apply_list()
    assert not written and 'target changed' in panel.status_line.text()
    panel.lab_check_target = lambda: None
    panel.preview_pairs()
    panel.apply_list()
    assert written == [plan]
    panel.close()


@pytest.mark.parametrize('title', [
    'Node Editing Lab', 'Stem Interpolation Lab', 'Kerning Recipe Lab',
    'Font Metadata Lab', 'Layer Transfer Lab',
])
def test_menu_launches_exact_named_writer_lab(title, monkeypatch, tmp_path):
    """App-owned launcher in the shape the Examples menu uses; App tests never read an Examples checkout.

    The real Examples launcher seam belongs to an opt-in integration test (TODO row).
    """
    import runpy
    from fontlabapp.fontui.teaching_writers import app

    called = []
    monkeypatch.setattr(app, 'show', called.append)
    path = tmp_path / (title + '.py')
    path.write_text(
        'def main() -> None:\n'
        '    from fly.ap.fontui.teaching_writers.app import show\n\n'
        f'    show({title!r})\n\n\n'
        'if __name__ == "__main__":\n'
        '    main()\n'
    )
    module = runpy.run_path(str(path))
    assert called == []
    module['main']()
    assert called == [title]
    called.clear()
    runpy.run_path(str(path), run_name='__main__')
    assert called == [title]


@pytest.mark.parametrize('module', ['stem_blend', 'scale_with_stem_compensation'])
def test_stored_outline_matches_when_native_integer_snaps_then_accepted_but_real_mismatch_fails(module):
    import importlib

    mod = importlib.import_module(f'fontlabapp.fontui.teaching_writers.{module}')
    want = [(True, [(5.5, 207.5, True), (10.0, 20.0, False)], False)]

    def got(x, y):
        return [(True, [(x, y, True), (10.0, 20.0, False)], False)]

    assert mod.stored_outline_matches(got(6.0, 208.0), want), 'FontLab stores 5.5 as 6'
    assert mod.stored_outline_matches(got(5.5, 207.5), want)
    assert not mod.stored_outline_matches(got(7.0, 208.0), want), 'off by 1.5 is real'
    assert not mod.stored_outline_matches(got(6.3, 208.0), want), 'non-integer drift is real'
    assert not mod.stored_outline_matches([(True, [(6.0, 208.0, False), (10.0, 20.0, False)], False)], want), 'node kind'
    assert not mod.stored_outline_matches([(False, got(6.0, 208.0)[0][1], False)], want), 'closure'


def test_require_no_editors_when_action_given_then_refusal_names_it():
    from fontlabapp.glyphs.unicode.duplicates import capture

    class Widget:
        def inherits(self, name):
            return True

    qt = type('Q', (), {'QtGui': type('G', (), {'QApplication': type('A', (), {'allWidgets': staticmethod(lambda: [Widget()])})})})
    with pytest.raises(ValueError, match='before writing to the font[.]$'):
        capture.require_no_editors(qt, float('inf'), 'writing to the font')
    with pytest.raises(ValueError, match='before removing Unicode assignments[.]$'):
        capture.require_no_editors(qt, float('inf'))
