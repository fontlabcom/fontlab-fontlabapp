# this_file: tests/test_wp05_raise_tab.py
"""Raise Ascender tab preserves the existing ordered backend scopes."""
import importlib
import sys
from types import SimpleNamespace as NS

import pytest
from _studio_qt import studio_qt  # noqa: F401


@pytest.fixture
def panel(studio_qt, monkeypatch):  # noqa: F811
    monkeypatch.delitem(sys.modules, 'fontlabapp.fontui.raise_ascender', raising=False)
    importlib.import_module('fontlabapp.fontui.raise_ascender')
    model = importlib.import_module('fontlabapp.contours.raise_ascender.model')
    source = model.Layer('a', 500, (model.Point(20, 510), model.Point(30, 511)))
    row = NS(source=source, name='A', layer=NS(name='Regular'))
    state = NS(rows=(row,))
    class Backend:
        def __init__(self):
            self.state, self.calls = state, []
        def capture(self, all_layers, deadline):
            self.calls.append(('capture', all_layers))
            return self.state
        def execute(self, amount, all_layers, disclosure):
            self.calls.append(('execute', amount, all_layers))
            return dict(nodes=1, occurrences=2, undo_steps=2)
    backend = Backend()
    shell = studio_qt.modules.appshell.AppShell('Raise', 'tglyph')
    studio = NS(shell=shell, preview=NS(load=lambda *a: None), package=lambda: backend)
    import fontlabapp.fontui as fontui
    view = fontui.raise_ascender_tab(studio, backend=backend)
    shell.add_tab(NS(title='Raise ascender', build=lambda shell: view))
    studio_qt.owned.append(shell)
    yield view, backend, shell, state


def test_raise_tab_when_preview_then_exact_scope_and_plan_acceptance(panel):
    view, backend, shell, state = panel
    assert not view.ready()
    shell.preview_button.click()
    assert view.ready()
    assert all(c[0] != 'execute' for c in backend.calls)
    view.amount.setText('20')
    assert not view.ready()
    shell.preview_button.click()
    backend.state = NS(rows=())
    assert not view.ready()
    backend.state = state
    view.scope.setCurrentIndex(1)
    shell.preview_button.click()
    shell.apply_button.click()
    assert ('execute', '20', True) in backend.calls
    assert '2 Undo steps' in shell.status.text()
    assert not view.ready()


def test_raise_tab_when_invalid_or_empty_then_no_write_and_refresh(panel):
    view, backend, shell, state = panel
    view.amount.setText('nan')
    shell.preview_button.click()
    assert 'finite' in shell.status.text()
    assert not view.ready()
    backend.state = NS(rows=())
    view.amount.setText('10')
    shell.preview_button.click()
    view.discard()
    assert not view.ready()
    assert not any(c[0] == 'execute' for c in backend.calls)


def test_raise_tab_when_backend_fails_then_discloses_partial_state(panel):
    view, backend, shell, state = panel
    def fail(*args, **kwargs):
        kwargs['disclosure']['pending_note'] = 'Pending updates remain.'
        raise RuntimeError('Partial native write; use Undo.')
    backend.execute = fail
    shell.preview_button.click()
    shell.apply_button.click()
    assert 'use Undo' in shell.status.text()
    assert 'Pending updates remain' in shell.status.text()
    assert not view.ready()


def test_raise_tab_when_lazy_backend_then_capture(panel, monkeypatch):
    view, backend, shell, state = panel
    module = importlib.import_module('fontlabapp.fontui.raise_ascender')
    monkeypatch.setattr(module, 'Backend', lambda: backend)
    view.backend = None
    shell.preview_button.click()
    assert view.backend is backend and view.ready()


def test_raise_tab_when_captured_font_changes_then_no_backend_action(panel):
    view, backend, shell, state = panel
    view.studio.package = lambda: object()
    shell.preview_button.click()
    assert not backend.calls
    assert 'captured font' in shell.status.text()


def test_raise_tab_when_row_selected_then_captured_layer_preview(panel):
    view, backend, shell, state = panel
    seen = []
    view.studio.preview = NS(load=lambda *args: seen.append(args))
    view.row_chosen('A', 'Aux')
    assert seen == [('A', 'Aux')]
    view.studio.preview = None
    view.row_chosen('A', 'Aux')


def test_raise_tab_when_row_context_is_stale_then_contains_refusal(panel):
    view, backend, shell, state = panel
    view.studio.package = lambda: None
    view.row_chosen('A', 'Regular')
    assert 'captured font' in shell.status.text()


def test_raise_tab_when_direct_apply_without_preview_then_refuse(panel):
    view, backend, shell, state = panel
    with pytest.raises(ValueError, match='Preview'):
        view.apply()
    assert not backend.calls
