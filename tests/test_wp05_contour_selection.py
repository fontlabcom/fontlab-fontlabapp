# this_file: tests/test_wp05_contour_selection.py
"""The selection studio stages exact existing plans and binds captured layers."""
import importlib
import sys
from types import SimpleNamespace as NS

import pytest
from _studio_qt import studio_qt as _studio_qt
from fontlabapp.contours.selection.model import Path
from PySide6 import QtCore

studio_qt = _studio_qt


@pytest.fixture
def studio(studio_qt, monkeypatch):
    monkeypatch.delitem(sys.modules, 'fontlabapp.fontui.contour_selection', raising=False)
    mod = importlib.import_module('fontlabapp.fontui.contour_selection')
    state = NS(paths=(Path((True, False, True), 50), Path((False, False), 100)), context=(1,))
    occurrence = NS(package=object(), package_id=1, glyph_id=2, layer_id=3, glyph_name='A', layer_name='Regular')
    calls = []
    monkeypatch.setattr(mod, 'capture', lambda **kw: NS(paths=state.paths, context=state.context))
    monkeypatch.setattr(mod, 'selected', lambda: occurrence)
    monkeypatch.setattr(mod, 'apply', lambda source, target: calls.append((source, target)) or target.paths)
    preview = studio_qt.modules.lifecycle.Owned(None)
    preview.load = lambda *a: calls.append(('load', a))
    preview.highlight = lambda **kw: calls.append(('highlight', kw))
    preview.refresh = lambda: None
    shell = mod.show(font=lambda: object(), preview=lambda *a, **kw: preview)
    studio_qt.owned.append(shell)
    return NS(mod=mod, shell=shell, state=state, calls=calls, preview=preview)


def test_three_modes_preserve_original_selection_plans(studio):
    shell = studio.shell
    assert shell.tabs.count() == 4
    for tab, expected in zip(shell.selection_tabs, (((True, True, True), (False, False)), ((True, True, True), (False, False)), ((True, True, True), (False, False)))):
        target = tab.preview_changes()
        assert target.nodes == expected
        assert tab.ready()
        assert tab.apply_changes() == target.paths
    assert len([x for x in studio.calls if not isinstance(x[0], str)]) == 3


def test_apply_requires_preview_and_same_input_and_captured_selection(studio):
    tab = studio.shell.selection_tabs[2]
    with pytest.raises(ValueError, match='Preview'):
        tab.apply_changes()
    tab.preview_changes()
    tab.limit.setText('nan')
    assert not tab.ready()
    with pytest.raises(ValueError):
        tab.preview_changes()
    assert tab.target is None
    tab.limit.setText('50')
    target = tab.preview_changes()
    assert target.paths == 0  # strict smaller-than; never <=
    studio.state.paths = (Path((False,), 2),)
    assert not tab.ready()
    with pytest.raises(ValueError, match='changed'):
        tab.apply_changes()


def test_preview_and_sorting_never_write_and_refresh_refuses_staged_plan(studio):
    tab = studio.shell.selection_tabs[0]
    tab.preview_changes()
    tab.table.proxy.sort(1, QtCore.Qt.DescendingOrder)
    tab.table.select('A', 'Regular')
    assert ('load', ('A', 'Regular')) in studio.calls
    studio.shell._run_action('refresh')
    assert 'discard staged' in studio.shell.status.text()
    assert tab.target is not None
    tab.discard()
    assert tab.target is None
    studio.shell._run_action('refresh')
    assert not [x for x in studio.calls if not isinstance(x[0], str)]


def test_capture_failure_closes_constructed_shell(studio_qt, monkeypatch):
    monkeypatch.delitem(sys.modules, 'fontlabapp.fontui.contour_selection', raising=False)
    mod = importlib.import_module('fontlabapp.fontui.contour_selection')
    monkeypatch.setattr(mod, 'selected', lambda: (_ for _ in ()).throw(ValueError('No selection')))
    with pytest.raises(ValueError, match='No selection'):
        mod.show(font=lambda: object())


def test_bottom_apply_and_switched_occurrence_refusal(studio, monkeypatch):
    tab = studio.shell.selection_tabs[0]
    studio.shell._run_action('preview')
    studio.shell._run_action('apply')
    assert len([x for x in studio.calls if not isinstance(x[0], str)]) == 1
    monkeypatch.setattr(studio.mod, 'selected', lambda: NS(package_id=99, glyph_id=2, layer_id=3))
    with pytest.raises(ValueError, match='changed'):
        tab.refresh()
    monkeypatch.setattr(studio.preview, 'load', lambda *args: (_ for _ in ()).throw(RuntimeError('stale glyph')))
    tab.table.row_selected.emit('A', 'Regular')
    assert 'Preview unavailable: stale glyph' in studio.shell.status.text()
    studio.shell.close()
    assert studio.shell._close_complete
    assert not tab.connections and not tab.table.row_selected.slots


def test_failed_postconstruction_cleanup_keeps_shell_for_retry(studio, monkeypatch):
    shells = []
    original = studio.mod.fontui.app_shell
    def factory(*args, **kwargs):
        shell = original(*args, **kwargs)
        shells.append(shell)
        return shell
    monkeypatch.setattr(studio.mod.fontui, 'app_shell', factory)
    monkeypatch.setattr(studio.mod.SelectionTab, 'refresh', lambda self: (_ for _ in ()).throw(ValueError('capture failed')))
    monkeypatch.setattr(studio.preview, 'close', lambda: False)
    with pytest.raises(BaseException) as caught:
        studio.mod.show(font=lambda: object(), preview=lambda *a, **kw: studio.preview)
    assert caught.value.owner is shells[0]
    assert not shells[0]._close_complete
    monkeypatch.setattr(studio.preview, "close", type(studio.preview).close.__get__(studio.preview))
    shells[0].close()
    assert shells[0]._close_complete


def test_selected_requires_a_layer_and_returns_first_explicit_occurrence(studio_qt, monkeypatch):
    monkeypatch.delitem(sys.modules, 'fontlabapp.fontui.contour_selection', raising=False)
    module = importlib.import_module('fontlabapp.fontui.contour_selection')
    monkeypatch.setattr(module.selection, 'capture', lambda deadline: NS(occurrences=()))
    with pytest.raises(ValueError, match='Select a glyph layer'):
        module.selected()
    first = object()
    monkeypatch.setattr(module.selection, 'capture', lambda deadline: NS(occurrences=(first, object())))
    assert module.selected() is first


def test_changed_geometry_refuses_preview_before_any_setter(studio):
    studio.state.paths = (Path((False,), 2),)
    with pytest.raises(ValueError, match='Selection or geometry changed'):
        studio.shell.selection_tabs[0].preview_changes()
    assert not [x for x in studio.calls if not isinstance(x[0], str)]


def test_preview_creation_failure_preserves_original_error_after_clean_close(studio, monkeypatch):
    shells = []
    factory = studio.mod.fontui.app_shell
    def capture_shell(*args, **kwargs):
        shell = factory(*args, **kwargs)
        shells.append(shell)
        return shell
    monkeypatch.setattr(studio.mod.fontui, 'app_shell', capture_shell)
    def fail_preview(*args, **kwargs):
        raise ValueError('preview unavailable')
    with pytest.raises(ValueError, match='preview unavailable'):
        studio.mod.show(font=lambda: object(), preview=fail_preview)
    assert shells[0]._close_complete
