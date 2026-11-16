# this_file: tests/test_studio_kerning_proof.py
"""WP03 proof tabs keep exact symmetry staging, identities and writer failures."""

import importlib

import pytest
from _studio_qt import isolated_studio_modules, studio_qt  # noqa: F401
from test_kerning_symmetry_native import fixture


def stage(package):
    from fontlabapp.studios.kerning_proof.stage import SymmetryStage

    return SymmetryStage(lambda: package)


def test_symmetry_when_previewed_then_no_write_and_apply_exact_plan(monkeypatch):
    package, kerns, history, _, names = fixture(monkeypatch)
    task = stage(package)
    report = task.preview()
    assert report['applied'] is False
    assert report['result'] == 'Preview only; no kerning written.'
    assert report['masters'][0]['mismatches'][0]['warning']
    assert not history and task.ready()
    assert task.apply()['applied']
    assert kerns['Light'].values[names[1], names[0]] == -17
    assert not task.ready()
    with pytest.raises(ValueError, match='Preview'):
        task.apply()


@pytest.mark.parametrize('change', ['pairs', 'order', 'identity', 'font'])
def test_symmetry_when_stale_then_refuses_before_history(monkeypatch, change):
    package, kerns, history, _, names = fixture(monkeypatch)
    task = stage(package)
    task.preview()
    if change == 'pairs':
        kerns['Bold'].values[names[0], names[1]] = -5
    elif change == 'order':
        groups = kerns['Light'].groups
        groups['L'] = groups.pop('L')
    elif change == 'identity':
        package.findName(names[0]).id += 1
    else:
        task.package = lambda: None
    with pytest.raises(ValueError, match='changed|font'):
        task.apply()
    assert not history


def test_symmetry_when_zero_or_noop_then_preserves_original_policy(monkeypatch):
    package, kerns, history, _, names = fixture(monkeypatch)
    kerns['Light'].values[names[0], names[1]] = 0
    task = stage(package)
    task.preview()
    assert task.apply()['applied'] and not kerns['Light'].values
    count = len(history)
    task.preview()
    assert not task.ready()
    assert not task.apply()['applied'] and len(history) == count


def test_symmetry_when_capture_or_write_fails_then_no_false_acceptance(monkeypatch):
    package, kerns, history, _, names = fixture(monkeypatch)
    task = stage(package)
    task.preview()
    package.findName = lambda name: None
    with pytest.raises(ValueError, match='target'):
        task.preview()
    assert not task.ready() and not history
    package, kerns, history, _, names = fixture(monkeypatch)
    kerns['Bold'].values[names[0], names[1]] = -10
    kerns['Bold'].fail = True
    task = stage(package)
    task.preview()
    with pytest.raises(RuntimeError, match='partially changed.*Undo'):
        task.apply()
    assert not task.ready() and len(history) == 2


def test_symmetry_when_deadline_or_missing_font_then_no_capture(monkeypatch):
    from fontlabapp.studios.kerning_proof import stage as module

    monkeypatch.setattr(module, 'monotonic', lambda: 0)
    check = module.deadline_check()
    check()
    monkeypatch.setattr(module, 'monotonic', lambda: 3)
    with pytest.raises(TimeoutError):
        check()
    with pytest.raises(ValueError, match='font'):
        stage(None).preview()


@pytest.fixture
def proof_qt(isolated_studio_modules, studio_qt):  # noqa: F811
    yield studio_qt


def test_proof_shell_when_opened_then_tabs_preview_actions_and_symmetry(monkeypatch, proof_qt):
    package, kerns, history, _, names = fixture(monkeypatch)
    for kern in kerns.values():
        kern.get = lambda pair, kern=kern: kern.values.get(pair, 0)
    module = importlib.import_module('fontlabapp.studios.kerning_proof')
    shell = module.show(package=lambda: package, font=lambda: None, preview=lambda *args: None)
    proof_qt.owned.append(shell)
    assert [shell.tabs.tabText(i) for i in range(shell.tabs.count())] == [
        'Pairs From Text', 'Text Preview', 'Symmetry', 'About']
    symmetry = shell.kerning_proof_tabs['Symmetry']
    shell.tabs.setCurrentIndex(2)
    shell.apply_button.click()
    assert not history
    shell.preview_button.click()
    assert symmetry.stage.ready() and not history
    assert symmetry.table.rows
    shell.apply_button.click()
    assert kerns['Light'].values[names[1], names[0]] == -17
    assert not symmetry.stage.ready()
    shell.tabs.setCurrentIndex(1)
    assert shell.apply_button.isHidden()


def open_proof(monkeypatch, proof_qt, *, with_preview=True, empty=False):
    import fontlabapp.fontui as fontui
    from fontlabapp.studios.kerning_proof import show

    package, kerns, history, state, names = fixture(monkeypatch)
    for kern in kerns.values():
        kern.get = lambda pair, kern=kern: kern.values.get(pair, 0)
    package.ascender_value, package.descender_value = 800, -200
    from types import SimpleNamespace
    from PythonQt import QtGui
    path = QtGui.QPainterPath()
    path.addRect(0, 0, 500, 700)
    shape = SimpleNamespace(transform=QtGui.QTransform(), getContours=lambda: [SimpleNamespace(path=lambda: path)])
    for name in names:
        package.findName(name).findLayer = lambda master: SimpleNamespace(isNull=False, shapes=[shape], advanceWidth=600)
    calls = []

    class Preview(proof_qt.modules.lifecycle.Owned):
        def set_layer(self, layer):
            calls.append(('layer', layer))

        def set_text(self, text):
            calls.append(('text', text))

        def set_view(self, **kwargs):
            calls.append(('view', kwargs))

        def refresh(self):
            calls.append(('refresh',))

        def highlight_pair(self, left, right):
            calls.append(('pair', left, right))

    def factory(font, parent, **kwargs):
        assert kwargs['read_only'] and not kwargs['controls']
        return Preview(parent)

    monkeypatch.setattr(fontui, 'metrics_preview', factory)
    shell = show(package=lambda: None if empty else package,
                 font=lambda: object() if with_preview else None)
    proof_qt.owned.append(shell)
    return shell, kerns, history, state, names, calls


def test_pairs_when_sorted_and_ticked_then_add_explicit_values_on_all_masters(monkeypatch, proof_qt):
    shell, kerns, history, _, names, calls = open_proof(monkeypatch, proof_qt)
    panel = shell.kerning_proof_tabs['Pairs From Text']
    panel.text.setText('/a.sc/v.sc /w.sc/y.sc')
    panel.refresh()
    panel.grid.view.sortByColumn(0, proof_qt.QtCore.Qt.DescendingOrder)
    panel.grid.model.item(1, 0).setCheckState(proof_qt.QtCore.Qt.Unchecked)
    panel.mode.setCurrentIndex(1)
    panel.scope.setCurrentIndex(1)
    panel.value.setValue(5)
    assert panel.ticked() == [(names[0], names[1])]
    with pytest.raises(ValueError, match='Preview'):
        panel.apply()
    shell.preview_button.click()
    assert panel.ready() and not history
    shell.refresh_button.click()
    assert 'discard staged' in shell.status.text()
    panel.grid.select('  '.join((names[0], names[1])), 'Bold')
    assert ('pair', names[0], names[1]) in calls
    panel.value.setValue(6)
    assert not panel.ready()
    panel.value.setValue(5)
    shell.apply_button.click()
    assert kerns['Light'].values[names[0], names[1]] == -12
    assert kerns['Bold'].values[names[0], names[1]] == 5
    assert (names[2], names[3]) not in kerns['Bold'].values
    assert not panel.ready() and history
    panel.discard()


def test_pairs_when_controls_change_or_snapshot_stales_then_no_hidden_write(monkeypatch, proof_qt):
    shell, kerns, history, _, names, _ = open_proof(monkeypatch, proof_qt, with_preview=False)
    panel = shell.kerning_proof_tabs['Pairs From Text']
    panel.text.setText('/a.sc/v.sc')
    panel.preview_changes()
    assert panel.ready()
    kerns['Light'].values[names[0], names[1]] = -22
    with pytest.raises(ValueError, match='stale'):
        panel.apply()
    assert not history and not panel.ready()
    panel.refresh()
    panel.preview_changes()
    panel.text.setText('/v.sc/a.sc')
    assert not panel.ready()
    panel.preview_changes()
    assert panel.ready()
    panel.apply()
    assert (names[1], names[0]) in kerns['Bold'].values


def test_pairs_when_no_font_or_capture_changes_then_no_accepted_plan(monkeypatch, proof_qt):
    shell, _, history, _, _, _ = open_proof(monkeypatch, proof_qt, empty=True, with_preview=False)
    panel = shell.kerning_proof_tabs['Pairs From Text']
    panel.preview_changes()
    assert not panel.ready() and not history
    shell.kerning_proof_tabs['Text Preview'].refresh()
    shell, _, _, _, _, _ = open_proof(monkeypatch, proof_qt)
    panel = shell.kerning_proof_tabs['Pairs From Text']
    from fontlabapp.kerning import selection
    original = selection.text_values

    def mutate(package, *args):
        values = original(package, *args)
        package.kerning('Light').values['a.sc', 'v.sc'] = -88
        return values

    monkeypatch.setattr(selection, 'text_values', mutate)
    with pytest.raises(ValueError, match='changed'):
        panel.refresh()
    assert panel.snapshot is None


def test_text_controls_and_symmetry_rows_keep_selected_layer_and_refresh_preview(monkeypatch, proof_qt):
    shell, _, _, _, names, calls = open_proof(monkeypatch, proof_qt)
    panel = shell.kerning_proof_tabs['Text Preview']
    panel.text.setText('/a.sc/v.sc')
    panel.master.setCurrentIndex(0)
    panel.size.setValue(96)
    panel.kerned.setChecked(False)
    assert ('layer', 'Light') in calls
    assert ('view', {'size': 96, 'kerning': False}) in calls
    symmetry = shell.kerning_proof_tabs['Symmetry']
    symmetry.preview_changes()
    symmetry.table.select('  '.join(names[:2]), 'Light')
    assert ('pair', *names[:2]) in calls
    symmetry.apply()
    assert calls[-1] == ('refresh',)
    symmetry.refresh()
    assert not symmetry.table.rows and not symmetry.details.toPlainText()


def test_proof_when_preview_construction_fails_then_closes_shell(monkeypatch, proof_qt):
    import fontlabapp.fontui as fontui
    from fontlabapp.studios.kerning_proof import show

    created = []
    original = fontui.app_shell

    def factory(*args, **kwargs):
        shell = original(*args, **kwargs)
        created.append(shell)
        return shell

    def fail(*args):
        raise RuntimeError('preview failed')

    monkeypatch.setattr(fontui, 'app_shell', factory)
    with pytest.raises(RuntimeError, match='preview failed'):
        show(package=lambda: None, font=lambda: None, preview=fail)
    assert created[0].closed


def test_symmetry_when_capture_changes_during_preview_then_rejects_plan(monkeypatch):
    from fontlabapp.studios.kerning_proof import stage as module

    package, kerns, history, _, names = fixture(monkeypatch)
    task = stage(package)
    original = module.native.capture
    calls = []

    def capture(*args):
        if calls:
            kerns['Light'].values[names[0], names[1]] = -18
        calls.append(True)
        return original(*args)

    monkeypatch.setattr(module.native, 'capture', capture)
    with pytest.raises(ValueError, match='changed'):
        task.preview()
    assert not task.ready() and not history


def test_native_text_canvas_when_noncurrent_master_then_paints_exact_values(monkeypatch, proof_qt):
    shell, _, history, _, _, _ = open_proof(monkeypatch, proof_qt)
    panel = shell.kerning_proof_tabs['Text Preview']
    panel.text.setText('/a.sc/v.sc')
    panel.master.setCurrentIndex(0)
    assert panel.rows[-1][3] == -17
    assert '1 kerned gaps, -17 units' in shell.status.text()
    panel.canvas.resize(600, 240)
    image = panel.canvas.grab()
    assert not image.isNull() and panel.canvas.paint_error is None and not history
    panel.show_values.setChecked(False)
    assert not panel.canvas.grab().isNull()
    panel.kerned.setChecked(False)
    assert panel.rows[-1][3] == 0
    assert not panel.canvas.grab().isNull()
    panel.text.setText('')
    assert not panel.canvas.grab().isNull() and not panel.rows
    from fontlabapp.studios.kerning_proof.text import parse_text
    assert parse_text('A/unknown /a.sc //?', shell.package()) == ['uni65', 'a.sc']


def test_native_text_canvas_when_painter_or_owner_fails_then_cleanup_is_contained(monkeypatch, proof_qt):
    from fontlabapp.studios.kerning_proof import text

    shell, _, _, state, _, _ = open_proof(monkeypatch, proof_qt)
    panel = shell.kerning_proof_tabs['Text Preview']
    state.package = None
    panel.canvas.grab()
    assert 'no longer current' in panel.canvas.paint_error
    ended = []

    class Painter:
        def fillRect(self, *args):  # noqa: N802
            raise RuntimeError('paint failure')

        def end(self):
            ended.append(True)
            raise RuntimeError('end failure')

    monkeypatch.setattr(text.QtGui, 'QPainter', lambda *args: Painter())
    panel.canvas.paintEvent(None)
    assert ended == [True] and panel.canvas.paint_error == "RuntimeError('end failure')"

    def fail(*args):
        raise RuntimeError('owner gone')

    monkeypatch.setattr(panel.tool, 'say', fail)
    monkeypatch.setattr(text.QtGui, 'QPainter', fail)
    panel.canvas.paintEvent(None)
    assert panel.canvas.error_hook_failed and panel.canvas.paint_error == "RuntimeError('owner gone')"


def test_text_pairs_when_value_columns_sorted_then_numeric_order_and_tick_identity(monkeypatch, proof_qt):
    shell, kerns, _, _, names, _ = open_proof(monkeypatch, proof_qt, with_preview=False)
    kerns['Light'].values[names[0], names[1]] = -2
    kerns['Light'].values[names[2], names[3]] = -100
    panel = shell.kerning_proof_tabs['Pairs From Text']
    panel.text.setText('/a.sc/v.sc /w.sc/y.sc')
    panel.refresh()
    panel.grid.view.sortByColumn(1, proof_qt.QtCore.Qt.AscendingOrder)
    first_source = panel.grid.proxy.mapToSource(panel.grid.proxy.index(0, 0)).row()
    assert panel.pairs[first_source] == (names[2], names[3])
    panel.grid.model.item(first_source, 0).setCheckState(proof_qt.QtCore.Qt.Unchecked)
    assert panel.ticked() == [(names[0], names[1])]


def test_proof_when_source_getter_switches_then_all_plans_refuse_original_target(monkeypatch, proof_qt):
    from types import SimpleNamespace
    from fontlabapp.studios.kerning_proof import show

    package, kerns, history, state, _ = fixture(monkeypatch)
    for kern in kerns.values():
        kern.get = lambda pair, kern=kern: kern.values.get(pair, 0)
    shell = show(package=lambda: state.package, font=lambda: None)
    proof_qt.owned.append(shell)
    symmetry = shell.kerning_proof_tabs['Symmetry']
    symmetry.preview_changes()
    state.package = SimpleNamespace(id=99)
    with pytest.raises(ValueError, match='no longer current'):
        shell.package()
    with pytest.raises(ValueError, match='no longer current'):
        symmetry.apply()
    with pytest.raises(ValueError, match='no longer current'):
        shell.kerning_proof_tabs['Pairs From Text'].refresh()
    assert not history


def test_text_pairs_when_no_write_and_preview_fails_then_no_false_apply_claim(monkeypatch, proof_qt):
    shell, _, _, _, _, _ = open_proof(monkeypatch, proof_qt, with_preview=False)
    panel = shell.kerning_proof_tabs['Pairs From Text']
    panel.text.setText('/a.sc/v.sc')
    panel.refresh()
    panel.value.setValue(-50)
    panel.preview_changes()
    monkeypatch.setattr(panel.tool, 'write', lambda *args: False)

    def fail(*args):
        raise RuntimeError('preview broken')

    monkeypatch.setattr(panel, 'refresh', fail)
    with pytest.raises(RuntimeError, match='Kerning unchanged; preview failed') as error:
        panel.apply()
    assert 'Undo' not in str(error.value)
    assert panel.accepted is None and panel.snapshot is None
