# this_file: tests/test_studio_selected_actions.py
"""Staged selected-slot actions retain the original native write semantics."""
import importlib
from types import SimpleNamespace as NS

import pytest
import test_studio_current_pair as support

current_pair = support.current_pair
studio_qt = support.studio_qt
isolated_studio_modules = support.isolated_studio_modules


def test_selected_delete_requires_preview_and_refuses_changed_slot(current_pair, monkeypatch):
    f = current_pair
    module = importlib.import_module('fontlabapp.studios.kerning_studio.selected_delete')
    monkeypatch.setattr(module, 'selected_pairs', lambda: (f.package, [(f.rows[0], f.rows[1])]))
    stage = module.DeleteStage(lambda: f.package)
    with pytest.raises(ValueError, match='Preview'):
        stage.apply()
    report = stage.preview()
    assert report['removed'] == 1 and not f.history
    f.rows[1].index += 1
    with pytest.raises(ValueError, match='changed'):
        stage.apply()
    assert not f.history and not stage.ready()


def test_selected_delete_stages_complete_batch(current_pair, monkeypatch):
    f = current_pair
    module = importlib.import_module('fontlabapp.studios.kerning_studio.selected_delete')
    monkeypatch.setattr(module, 'selected_pairs', lambda: (f.package, [(f.rows[0], f.rows[1])]))
    stage = module.DeleteStage(lambda: f.package)
    stage.preview()
    assert stage.apply()['changed'] and len(f.history) == 2


def test_selected_steal_refuses_edited_height_without_writing(current_pair, monkeypatch):
    f = current_pair
    module = importlib.import_module('fontlabapp.studios.kerning_studio.selected_steal')
    stage = module.StealStage(lambda: f.package)
    monkeypatch.setattr(module, 'plan', lambda height, expected_id: {'height': height})
    writes = []
    monkeypatch.setattr(module, 'write', lambda value: writes.append(value) or {})
    with pytest.raises(ValueError, match='Preview'):
        stage.apply(100)
    stage.preview(100)
    assert stage.ready()
    with pytest.raises(ValueError, match='Height'):
        stage.apply(200)
    assert not writes and not stage.ready()
    stage.preview(100)
    assert stage.apply(100) == {} and writes == [{'height':100}]
    stage.package = lambda: NS(id=99)


def test_selected_panels_route_preview_apply_and_discard(current_pair, monkeypatch):
    from fontlabapp.studios import TabSpec
    from fontlabapp.studios._kerning import Tool
    f = current_pair
    delete = importlib.import_module('fontlabapp.studios.kerning_studio.selected_delete')
    steal = importlib.import_module('fontlabapp.studios.kerning_studio.selected_steal')
    shell = f.qt.modules.appshell.AppShell('Selected actions', 'tmetrics', package=lambda: f.package)
    f.qt.owned.append(shell)
    tool = Tool(shell, 'Kerning Studio', font=lambda: None)
    tool.reload()
    calls = []
    tool.preview = NS(set_text=lambda *args: calls.append(args), set_layer=lambda *args: calls.append(args),
                      highlight_pair=lambda *args: calls.append(args), refresh=lambda: calls.append('refresh'))
    panel = delete.DeletePanel(tool)
    shell.add_tab(TabSpec('Delete', lambda owner: panel.widget))
    shell.preview_button.click()
    assert panel.stage.ready() and panel.grid.rows
    shell.apply_button.click()
    assert calls[-1] == 'refresh' and 'Removed' in shell.status.text()
    panel.preview()
    panel.apply()
    assert 'No kerning' in shell.status.text()
    panel.refresh()
    assert not panel.grid.rows and not panel.stage.ready()
    matching = steal.StealPanel(tool)
    shell.add_tab(TabSpec('Steal', lambda owner: matching.widget))
    shell.tabs.setCurrentWidget(matching.widget)
    monkeypatch.setattr(steal, 'default_height', lambda package: 250)
    data = {'names': ('A','V','T','o'), 'edits': {'Light': {}}, 'record': 'A V',
            'height': 250, 'value': -25, 'gaps': (100,75), 'notices': ['open skipped']}
    monkeypatch.setattr(matching.stage, 'preview', lambda height: data)
    monkeypatch.setattr(matching.stage, 'apply', lambda height: {'changed': True, 'value': -25, 'notices': []})
    matching.preview()
    assert matching.height_edit.text() == '250' and matching.grid.rows
    matching.height_edit.setText('100')
    assert not matching.grid.rows
    matching.apply()
    assert calls[-1] == 'refresh' and 'set to -25' in shell.status.text()
    monkeypatch.setattr(matching.stage, 'apply', lambda height: {'changed': False, 'value': 0, 'notices': []})
    matching.apply()
    assert 'Pair record already absent.' in shell.status.text()
    monkeypatch.setattr(matching.stage, 'apply', lambda height: {'changed': True, 'value': 0, 'notices': []})
    matching.apply()
    assert 'Pair record removed.' in shell.status.text()


@pytest.mark.parametrize('problem', ['font', 'context', 'count', 'block', 'index', 'auxiliary', 'cross_master', 'undeclared'])
def test_delete_capture_refuses_invalid_context(current_pair, problem):
    f = current_pair
    module = importlib.import_module('fontlabapp.studios.kerning_studio.selected_delete')
    if problem == 'font':
        f.state.package = None
    elif problem == 'context':
        f.capture.context = (f.package.id, 'Light', 'font')
    elif problem == 'count':
        f.capture.occurrences = []
    elif problem == 'block':
        f.rows[1].block_id += 1
    elif problem == 'index':
        f.rows[1].index += 1
    elif problem == 'auxiliary':
        f.rows[0].layer.isMasterLayer = False
    elif problem == 'cross_master':
        f.rows[0].layer.name = 'Bold'
    else:
        for occurrence in f.rows:
            occurrence.layer.name = 'Missing'
    with pytest.raises(ValueError):
        module.run()
    assert not f.history


def test_delete_classes_keeps_exceptions_and_refuses_ambiguity(current_pair):
    f = current_pair
    module = importlib.import_module('fontlabapp.studios.kerning_studio.selected_delete')
    f.kerns['Light'].groups['L'] = ([f.names[0]], 'KernLeft')
    f.kerns['Light'].values['@L', f.names[1]] = -50
    report = module.run()
    assert report['removed'] == 1 and report['overrides']
    assert f.kerns['Light'].values[f.names[0], f.names[1]] == -17
    f.kerns['Light'].groups['Other'] = ([f.names[0]], 'KernBothSide')
    with pytest.raises(ValueError, match='multiple'):
        module.run()
    stage = module.DeleteStage(lambda: None)
    f.kerns['Light'].groups.pop('Other')
    with pytest.raises(ValueError, match='original font'):
        stage.preview()


def test_selected_delete_preview_discloses_kept_exceptions(current_pair):
    from fontlabapp.studios import TabSpec
    from fontlabapp.studios._kerning import Tool
    f = current_pair
    module = importlib.import_module('fontlabapp.studios.kerning_studio.selected_delete')
    f.kerns['Light'].groups['L'] = ([f.names[0]], 'KernLeft')
    f.kerns['Light'].values['@L', f.names[1]] = -50
    shell = f.qt.modules.appshell.AppShell('Delete preview', 'tmetrics', package=lambda: f.package)
    f.qt.owned.append(shell)
    tool = Tool(shell, 'Kerning Studio', font=lambda: None)
    tool.reload()
    panel = module.DeletePanel(tool)
    shell.add_tab(TabSpec('Delete', lambda owner: panel.widget))
    shell.preview_button.click()
    assert f"Light: {f.names[0]} · {f.names[1]} = -17" in shell.status.text()
    assert '1 records to remove' in shell.status.text() and not f.history
