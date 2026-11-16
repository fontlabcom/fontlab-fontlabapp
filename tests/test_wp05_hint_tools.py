# this_file: tests/test_wp05_hint_tools.py
"""Hint Tools accepted-plan guards and preserved directional writer policies."""
from types import SimpleNamespace as NS

import pytest


def test_session_requires_preview_and_refuses_changed_font(monkeypatch):
    from fontlabapp.studios.hint_tools.session import Session
    package = NS(id=1, master='Regular', masters=['Regular'])
    live = [package]
    session = Session(lambda: live[0], lambda: ['A'])
    with pytest.raises(ValueError, match='Preview'):
        session.apply('remove', False, False, True, True)
    live[0] = NS(id=2)
    with pytest.raises(ValueError, match='font'):
        session.package()


def test_session_rechecks_snapshot_before_write(monkeypatch):
    from fontlabapp.studios.hint_tools import session as module
    package = NS(id=1, master='Regular', masters=['Regular'])
    state = [1]
    row = NS(glyph=NS(name='A'), master='Regular', layer=object(), before=(2, 3), note='')
    monkeypatch.setattr(module.history, 'scan_auto_facts', lambda p: ())
    monkeypatch.setattr(module.removal, 'survey', lambda *a: [row])
    monkeypatch.setattr(module, 'snapshot', lambda layer: state[0])
    calls = []
    monkeypatch.setattr(module.removal, 'remove_hints', lambda *a: calls.append(a) or {'layers': 1})
    session = module.Session(lambda: package, lambda: ['A'])
    assert session.preview('remove', False, False, True, False) == [row]
    state[0] = 2
    with pytest.raises(ValueError, match='changed'):
        session.apply('remove', False, False, True, False)
    assert not calls
    session.preview('remove', False, False, True, False)
    assert session.apply('remove', False, False, True, False) == {'layers': 1}
    assert len(calls) == 1
    with pytest.raises(ValueError, match='Preview'):
        session.apply('remove', False, False, True, False)


def test_models_preserve_hint_policies(monkeypatch):
    from fontlabapp.studios.hint_tools import autohint, removal
    import fontlabapp.hints.postscript as hints
    import fontlabapp.core.history.glyphs as history
    layer = NS(isNull=False, autoLayer=False, isLocked=False,
               shapes=[NS(isComponent=False, contours=[object()])], counts=(2, 3))
    glyph = NS(name='A', isNull=False, findLayer=lambda name: layer if name == 'R' else None)
    package = NS(findName=lambda name: glyph if name == 'A' else None)
    monkeypatch.setattr(hints, 'hint_counts', lambda layer: layer.counts)
    monkeypatch.setattr(history, 'refusal', lambda *a, **k: '')
    def commit(title, layers, glyphs, mutate, **kwargs):
        mutate()
        return NS(pending_note='queued', pending_updates=(7,), mismatches=kwargs['read_back']())
    monkeypatch.setattr(history, 'commit', commit)
    layer.autohint = lambda: setattr(layer, 'counts', (4, 5))
    layer.removeHints = lambda h, v: setattr(layer, 'counts', (0 if h else layer.counts[0], 0 if v else layer.counts[1]))
    for model in (autohint, removal):
        rows = model.survey(package, ['missing', 'A'], ['missing', 'R'], (), False)
        assert rows[0].note == 'no layer in this master'
        assert rows[1].before == (2, 3)
    rows = autohint.survey(package, ['A'], ['R'], (), False)
    assert autohint.autohint(rows, (), False)['after'] == {('A', 'R'): (4, 5)}
    rows = removal.survey(package, ['A'], ['R'], (), False)
    assert removal.remove_hints(rows, True, False, (), False)['removed'] == 4
    assert layer.counts == (0, 5)
    assert removal.remove_hints([], True, True, (), False)['layers'] == 0
    assert autohint.autohint([], (), False)['layers'] == 0
    with pytest.raises(ValueError, match='direction'):
        removal.survey(package, ['A'], ['R'], (), False, False, False)
    assert removal.direction_word(True, True) == ''
    assert removal.direction_word(True, False) == 'horizontal '
    assert removal.direction_word(False, True) == 'vertical '
    for model in (autohint, removal):
        options = (True, True) if model is removal else ()
        layer.autoLayer = True
        assert 'auto' in model.layer_note(layer, '', *options)
        layer.autoLayer = False
        assert 'dependency' in model.layer_note(layer, 'dependency', *options)
        layer.isLocked = True
        assert 'locked' in model.layer_note(layer, '', *options)
        layer.isLocked = False
    layer.shapes = []
    assert 'no outline' in autohint.layer_note(layer, '')
    layer.counts = (0, 0)
    assert 'no' in removal.layer_note(layer, '', True, True)
    layer.shapes = [NS(isComponent=False, contours=[object()])]
    layer.autohint = lambda: None
    assert autohint.autohint(rows, (), False)['mismatches']
    layer.counts = (2, 3)
    layer.removeHints = lambda h, v: None
    assert removal.remove_hints(rows, True, True, (), False)['mismatches']
    monkeypatch.setattr(history, 'refusal', lambda *a, **k: 'dependency')
    for model in (autohint, removal):
        assert model.survey(package, ['A'], ['R'], (), False)[0].before == (0, 0)


def test_session_other_paths(monkeypatch):
    from fontlabapp.studios.hint_tools import session as module
    with pytest.raises(ValueError, match='Open a font'):
        module.Session(lambda: None, lambda: [])
    package = NS(id=1, master='R', masters=['R', 'B'])
    chosen = ['A']
    session = module.Session(lambda: package, lambda: chosen)
    monkeypatch.setattr(module.history, 'scan_auto_facts', lambda p: ())
    row = NS(glyph=NS(name='A'), master='R', layer=None, before=(0, 0), note='locked')
    monkeypatch.setattr(module.autohint, 'survey', lambda *a: [row])
    monkeypatch.setattr(module.autohint, 'autohint', lambda *a: {'layers': 0})
    session.preview('autohint', True, False, True, True)
    assert session.apply('autohint', True, False, True, True) == {'layers': 0}
    with pytest.raises(ValueError, match='Unknown'):
        session.preview('unknown', True, False, True, True)
    chosen.clear()
    session.refresh()
    with pytest.raises(ValueError, match='Select glyphs'):
        session.preview('remove', True, False, True, True)


from _studio_qt import studio_qt  # noqa: E402, F401


def test_hint_window_actions_and_owned_close(studio_qt, monkeypatch):  # noqa: F811
    import importlib
    import sys
    monkeypatch.delitem(sys.modules, 'fontlabapp.fontui.hint_tools', raising=False)
    app = importlib.import_module('fontlabapp.fontui.hint_tools')
    package = NS(id=1, master='R', masters=['R'])
    canvas = studio_qt.modules.lifecycle.Owned(None)
    calls = []
    canvas.load = lambda name, layer: calls.append((name, layer))
    canvas.refresh = lambda: calls.append('refresh')
    shell = app.show(package=lambda: package, selection=lambda: ['A'], preview=lambda shell: canvas)
    studio_qt.owned.append(shell)
    assert [shell.tabs.tabText(i) for i in range(shell.tabs.count())] == ['Autohint', 'Remove PostScript hints', 'About']
    tab = next(child for child in shell.children if isinstance(child, app.HintTab))
    row = NS(glyph=NS(name='A'), master='R', before=(2, 3), note='', layer=object())
    monkeypatch.setattr(tab.session, 'preview', lambda *o: [row])
    monkeypatch.setattr(tab.session, 'apply', lambda *o: {'layers': 1})
    monkeypatch.setattr(app, 'hint_counts', lambda layer: (4, 5))
    assert tab.preview() == [row]
    assert calls[-1] == ('A', 'R')
    assert tab.apply() == {'layers': 1}
    assert calls[-1] == 'refresh'
    tab.discard()
    tab.refresh()
    shell.preview = None
    tab.row_selected('A', 'R')
    tab.apply()
    monkeypatch.setattr(tab.session, 'package', lambda: (_ for _ in ()).throw(ValueError('expired')))
    tab.row_selected('A', 'R')
    assert shell.status.text() == 'expired'
    assert tab.options() == ('autohint', False, False, True, True)
    with pytest.raises(ValueError, match='Open a font'):
        app.show(package=lambda: None, selection=lambda: [])
    monkeypatch.setattr(app.fontui, 'glyph_view', lambda *a, **k: studio_qt.modules.lifecycle.Owned(None))
    from fontlabapp.studios.hint_tools import show
    other = show(package=lambda: package, selection=lambda: [], font=lambda: object())
    studio_qt.owned.append(other)


def test_failed_preview_revokes_previous_acceptance(monkeypatch):
    from fontlabapp.studios.hint_tools.session import Session
    package = NS(id=1, master='R', masters=['R'])
    session = Session(lambda: package, lambda: ['A'])
    session.accepted = ('previous',)
    monkeypatch.setattr(session, 'capture', lambda *args: (_ for _ in ()).throw(ValueError('bad options')))
    with pytest.raises(ValueError, match='bad options'):
        session.preview('remove', False, False, False, False)
    assert session.accepted is None


def test_failed_hint_window_cleanup_preserves_owner(studio_qt, monkeypatch):  # noqa: F811
    import importlib
    import sys
    monkeypatch.delitem(sys.modules, 'fontlabapp.fontui.hint_tools', raising=False)
    app = importlib.import_module('fontlabapp.fontui.hint_tools')
    close = app.AppShell.close
    monkeypatch.setattr(app.AppShell, 'close', lambda self: (_ for _ in ()).throw(RuntimeError('disconnect failed')))
    with pytest.raises(Exception) as caught:
        app.show(package=lambda: None, selection=lambda: [])
    owner = caught.value.owner
    assert isinstance(owner, app.AppShell)
    monkeypatch.setattr(app.AppShell, 'close', close)
    owner.close()
    assert owner._close_complete


def test_bottom_actions_preserve_plan_and_show_actual_after_counts(studio_qt, monkeypatch):  # noqa: F811
    import importlib
    import sys
    monkeypatch.delitem(sys.modules, 'fontlabapp.fontui.hint_tools', raising=False)
    app = importlib.import_module('fontlabapp.fontui.hint_tools')
    from fontlabapp.studios.hint_tools import session as model
    package = NS(id=1, master='R', masters=['R'])
    layer = NS(counts=(2, 3))
    monkeypatch.setattr(model.history, 'scan_auto_facts', lambda p: ())
    monkeypatch.setattr(model, 'snapshot', lambda layer: 1)
    monkeypatch.setattr(model.autohint, 'survey', lambda *args: [
        NS(glyph=NS(name='A'), master='R', before=layer.counts, layer=layer, note='')])
    def write(*args):
        layer.counts = (4, 5)
        return {'layers': 1, 'after': {('A', 'R'): (4, 5)}, 'mismatches': [], 'pending_note': 'queued'}
    monkeypatch.setattr(model.autohint, 'autohint', write)
    monkeypatch.setattr(app, 'hint_counts', lambda layer: layer.counts)
    canvas = studio_qt.modules.lifecycle.Owned(None)
    canvas.load = lambda *args: None
    canvas.refresh = lambda: None
    shell = app.show(package=lambda: package, selection=lambda: ['A'], preview=lambda shell: canvas)
    studio_qt.owned.append(shell)
    tab = next(child for child in shell.children if isinstance(child, app.HintTab))
    shell.apply_button.click()
    assert layer.counts == (2, 3)
    shell.preview_button.click()
    accepted = tab.session.accepted
    assert tab.table.rows[0].values == ('R', 2, 3, '', '', 'Ready')
    shell.refresh_button.click()
    assert tab.session.accepted == accepted and 'discard' in shell.status.text()
    shell.apply_button.click()
    assert tab.table.rows[0].values == ('R', 2, 3, 4, 5, 'Applied')
    assert tab.session.accepted is None and 'queued' in shell.status.text()
    tab.discard()
    monkeypatch.setattr(tab.session, 'preview', lambda *options: [])
    assert tab.preview() == []


@pytest.mark.parametrize('suffix', ['autohint', 'removal'])
def test_legacy_hint_panel_contract_remains_callable(studio_qt, monkeypatch, suffix):  # noqa: F811
    import importlib
    import runpy
    from fontlabapp.contours.selection.panel import model as selection
    import fontlabapp.core.history.glyphs as history
    from fontlabapp.core import scripting
    class Base:
        def add_row(self, *args):
            self.controls = args
        def watch(self, signal):
            return None
        def consented(self):
            return False
    monkeypatch.setattr(selection, 'panel_type', lambda: Base)
    module = importlib.import_module('fontlabapp.fontui.hint_' + suffix)
    panel = module.panel_type()()
    panel.build_controls()
    panel.names = ['A']
    panel.facts = 'captured'
    row = NS(glyph=NS(name='A'), master='R', before=(2, 3), note='')
    monkeypatch.setattr(module, 'survey', lambda *args: [row])
    assert panel.plan_rows(object(), ['R']) == [row]
    assert panel.cells(row)[0] == 'A · R'
    row.note = 'locked'
    assert panel.cells(row) == ['A · R', 'locked']
    row.note = ''
    assert panel.pending([row]) and panel.pending([])
    monkeypatch.setattr(history, 'scan_auto_facts', lambda package: 'fresh')
    result = {'layers': 1, 'glyphs': 1, 'removed': 5, 'after': {('A', 'R'): (4, 5)}}
    if suffix == 'autohint':
        monkeypatch.setattr(module, 'autohint', lambda *args: result)
        panel.on_result(result)
        assert panel.cells(row)[2] == '4 / 5'
        panel.on_reselect()
        assert panel.after == {}
    else:
        monkeypatch.setattr(module, 'remove_hints', lambda *args: result)
        panel.horizontal.setChecked(False)
        assert panel.cells(row)[2] == '2 / 0'
        panel.vertical.setChecked(False)
        assert panel.directions() == (False, False)
    assert panel.write(object(), [row]) == result
    assert panel.result_text(result)
    assert panel.result_text({'layers': 0}).startswith('Nothing')
    calls = []
    monkeypatch.setattr(scripting, 'show_script_dialog', lambda cls, key: calls.append(key))
    module.main()
    runpy.run_path(module.__file__, run_name='__main__')
    assert calls == [module.KEY, module.KEY]
