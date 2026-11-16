# this_file: tests/test_studio_current_pair.py
"""Selected Glyph-window slot contract for the original Kern To Max action."""

import importlib
from types import SimpleNamespace as NS

import pytest
from _studio_qt import isolated_studio_modules, studio_qt  # noqa: F401
from test_kerning_symmetry_native import fixture


@pytest.fixture
def current_pair(monkeypatch, isolated_studio_modules, studio_qt):  # noqa: F811
    module = importlib.import_module('fontlabapp.studios.kerning_studio.current_pair')
    package, kerns, history, state, names = fixture(monkeypatch)
    rows = [NS(block_id=5, index=i, glyph_name=name, glyph_id=100+i, layer_id=200+i,
               layer=NS(isMasterLayer=True, name='Light', advanceWidth=501 + 100*i))
            for i, name in enumerate(names[:2])]
    capture = NS(context=(package.id, package.master, 'editor'), occurrences=rows)
    monkeypatch.setattr(module.selection, 'capture', lambda deadline: capture)
    yield NS(module=module, package=package, kerns=kerns, history=history, state=state,
             rows=rows, capture=capture, names=names, qt=studio_qt)


def test_selected_pair_when_previewed_then_exact_typed_limit_and_no_early_write(current_pair):
    f = current_pair
    task = f.module.CurrentPairStage(lambda: f.package)
    report = task.preview()
    assert report['value'] == -250 and not f.history
    assert task.ready()
    assert task.apply()['changed']
    assert f.kerns['Light'].values[f.names[0], f.names[1]] == -250
    assert not f.kerns['Bold'].values and not task.ready()
    with pytest.raises(ValueError, match='Preview'):
        task.apply()


@pytest.mark.parametrize('problem', ['font', 'context', 'count', 'active_extra', 'block', 'index', 'auxiliary', 'cross_master', 'undeclared'])
def test_selected_pair_when_invalid_slots_then_refuses_without_write(current_pair, problem):
    f = current_pair
    if problem == 'font':
        f.state.package = None
    elif problem == 'context':
        f.capture.context = (f.package.id, f.package.master, 'font')
    elif problem == 'count':
        f.capture.occurrences = f.rows[:1]
    elif problem == 'active_extra':
        f.capture.occurrences = f.rows + [f.rows[0]]
    elif problem == 'block':
        f.rows[1].block_id += 1
    elif problem == 'index':
        f.rows[1].index += 1
    elif problem == 'auxiliary':
        f.rows[0].layer.isMasterLayer = False
    elif problem == 'cross_master':
        f.rows[1].layer.name = 'Bold'
    else:
        for row in f.rows:
            row.layer.name = 'Absent'
    with pytest.raises(ValueError):
        f.module.CurrentPairStage(lambda: f.package).preview()
    assert not f.history


@pytest.mark.parametrize('width', [-1, float('nan'), float('inf')])
def test_selected_pair_when_invalid_advance_then_refuses(current_pair, width):
    current_pair.rows[0].layer.advanceWidth = width
    with pytest.raises(ValueError, match='finite and nonnegative'):
        current_pair.module.run()
    assert not current_pair.history


def test_selected_pair_when_classes_then_retains_overrides_and_refuses_ambiguous_membership(current_pair):
    f = current_pair
    f.kerns['Light'].groups['L'] = ([f.names[0]], 'KernLeft')
    f.kerns['Light'].groups['R'] = ([f.names[1]], 'KernRight')
    task = f.module.CurrentPairStage(lambda: f.package)
    report = task.preview()
    assert report['overrides'] == [f'Light: {f.names[0]} · {f.names[1]} = -17']
    task.apply()
    assert f.kerns['Light'].values['@L', '@R'] == -250
    assert f.kerns['Light'].values[f.names[0], f.names[1]] == -17
    f.kerns['Light'].groups['Other'] = ([f.names[0]], 'KernBothSide')
    with pytest.raises(ValueError, match='multiple kerning groups'):
        task.preview()
    assert not task.ready()


@pytest.mark.parametrize('change', ['selection', 'width', 'kerning', 'source'])
def test_selected_pair_when_changed_after_preview_then_no_write(current_pair, change):
    f = current_pair
    source = NS(package=f.package)
    task = f.module.CurrentPairStage(lambda: source.package)
    task.preview()
    if change == 'selection':
        f.rows[1].layer_id += 1
    elif change == 'width':
        f.rows[0].layer.advanceWidth += 1
    elif change == 'kerning':
        f.kerns['Bold'].values[f.names[0], f.names[1]] = -1
    else:
        source.package = NS(id=99)
    with pytest.raises(ValueError, match='changed|stale|original'):
        task.apply()
    assert not f.history and not task.ready()


def test_selected_pair_when_existing_limit_then_noop_and_zero_remain_distinct(current_pair):
    f = current_pair
    f.kerns['Light'].values[f.names[0], f.names[1]] = -250
    result = f.module.run()
    assert set(result) == {'value', 'changed', 'overrides'}
    assert not result['changed'] and not f.history
    f.rows[0].layer.advanceWidth = 0
    assert f.module.run()['value'] == 0
    assert f.kerns['Light'].values[f.names[0], f.names[1]] == 0


def test_current_pair_panel_when_preview_applied_then_bottom_actions_use_captured_scope(current_pair):
    from fontlabapp.studios import TabSpec
    from fontlabapp.studios._kerning import Tool

    f = current_pair
    shell = f.qt.modules.appshell.AppShell('Selected pair', 'tmetrics', package=lambda: f.package)
    f.qt.owned.append(shell)
    tool = Tool(shell, 'Kerning Studio', font=lambda: None)
    tool.reload()
    panel = f.module.CurrentPairPanel(tool)
    shell.add_tab(TabSpec('Kern To Max', lambda owner: panel.widget))
    shell.apply_button.click()
    assert not f.history
    shell.preview_button.click()
    assert panel.grid.rows[0].layer == 'Light' and panel.stage.ready()
    shell.refresh_button.click()
    assert panel.stage.ready() and 'discard staged' in shell.status.text()
    shell.apply_button.click()
    assert f.kerns['Light'].values[f.names[0], f.names[1]] == -250
    calls = []
    tool.preview = NS(set_text=lambda *args: calls.append(args), set_layer=lambda *args: calls.append(args),
                      highlight_pair=lambda *args: calls.append(args), refresh=lambda: calls.append('refresh'))
    panel.preview()
    panel.apply()
    assert calls[-1] == 'refresh' and 'Unchanged' in shell.status.text()
    panel.refresh()
    assert not panel.grid.rows


def test_selected_pair_when_source_changes_during_capture_or_write_fails_then_no_reusable_plan(current_pair, monkeypatch):
    f = current_pair
    task = f.module.CurrentPairStage(lambda: None)
    with pytest.raises(ValueError, match='original font'):
        task.preview()
    original = f.module.kerning.snapshot_kerning

    def snapshot(*args, **kwargs):
        result = original(*args, **kwargs)
        f.rows[0].layer.advanceWidth += 10
        return result

    task = f.module.CurrentPairStage(lambda: f.package)
    monkeypatch.setattr(f.module.kerning, 'snapshot_kerning', snapshot)
    with pytest.raises(ValueError, match='during preview'):
        task.preview()
    assert not task.ready() and not f.history
    monkeypatch.setattr(f.module.kerning, 'snapshot_kerning', original)
    task.preview()
    f.kerns['Light'].fail = True
    with pytest.raises(RuntimeError, match='partially changed.*Undo'):
        task.apply()
    assert not task.ready()
