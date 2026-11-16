# this_file: tests/test_wp08_context_proof.py
"""Context Proof retains every original mode and exact generator contract."""

import sys
from types import SimpleNamespace

import pytest
pytest_plugins = ["_studio_qt"]


@pytest.fixture(autouse=True)
def cleanup():
    yield
    for name in tuple(sys.modules):
        if name.startswith('fontlabapp.studios.proof_studio'):
            sys.modules.pop(name, None)


def test_context_routes_preserve_all_modes_and_empty_repeated_input():
    from fontlabapp.studios.proof_studio.practical import context_generators
    from fontlabapp.studios.proof_studio.generators import Options, generators

    originals = {g.key: g for g in generators()}
    routes = context_generators()
    assert len(routes) == 8
    assert len({g.title for g in routes}) == 8
    for route in routes:
        original = originals[route.key]
        assert route.make is original.make
        assert route.open is original.open
        assert route.title == original.scripts[route.choices[0][1]]
        for names in ((), ('A',), ('A', 'A', 'unencoded.alt')):
            options = Options(names=names)
            key = route.choices[0][1]
            assert route.make(key, options) == original.make(key, options)


def test_context_shell_has_named_tabs_read_only_preview_and_bottom_actions(studio_qt):
    from fontlabapp.studios.proof_studio.practical import show_context
    from fontlabapp.qt.properties import value
    from PythonQt import QtGui

    calls = []
    preview = QtGui.QWidget()
    preview.set_text = lambda text: calls.append(text)
    shell = show_context(font=lambda: object(), selection=lambda: ('A', 'A'),
                         preview=lambda shell, studio: preview, package=lambda: None)
    studio_qt.owned.append(shell)
    assert shell.title == 'Context Proof'
    assert value(shell.tabs, 'count') == 9
    assert shell.tabs.tabText(0) == 'Glyphs Between Lining Figures'
    assert 'Pedro Arilla' in value(shell.about, 'text')
    for index in range(8):
        shell.tabs.setCurrentIndex(index)
        assert shell.refresh_button.isEnabled()
        assert shell.preview_button.isEnabled()
        assert shell.apply_button.isHidden()
        shell.preview_button.click()
        assert calls[-1]
    shell.close()


# App-owned stand-in with the same shape as the Scriptmix launcher: lazy import inside main().
LAUNCHER_SHAPE = '''"""Context Proof launcher shape."""


def main() -> None:
    from fly.ap.studios.proof_studio.practical import show_context
    show_context()


if __name__ == "__main__":
    main()
'''


def test_context_menu_dispatches_lazily(monkeypatch, tmp_path):
    import runpy
    calls = []
    monkeypatch.setitem(sys.modules, 'fly.ap.studios.proof_studio.practical',
                        SimpleNamespace(show_context=lambda: calls.append('context')))
    path = tmp_path / 'Context Proof.py'
    path.write_text(LAUNCHER_SHAPE, encoding='utf-8')
    namespace = runpy.run_path(str(path))
    assert calls == []
    namespace['main']()
    runpy.run_path(str(path), run_name='__main__')
    assert calls == ['context', 'context']


def test_font_switch_refuses_selection_and_native_open(studio_qt, monkeypatch):
    from fontlabapp.studios.proof_studio.practical import show_context
    from fontlabapp.studios.proof_studio.generators import _context
    from fontlabapp.qt.properties import value
    from PythonQt import QtGui

    active = [SimpleNamespace(id=1)]
    selected, opened = [], []
    monkeypatch.setattr(_context, 'context_proof_api', lambda: SimpleNamespace(
        proof_lines=lambda mode, names: (names,), run=lambda mode: opened.append(active[0].id)))
    preview = QtGui.QWidget()
    preview.set_text = lambda text: None
    shell = show_context(font=lambda: object(), selection=lambda: selected.append(active[0].id) or ('A',),
                         preview=lambda shell, studio: preview, package=lambda: active[0])
    studio_qt.owned.append(shell)
    count = len(selected)
    active[0] = SimpleNamespace(id=2)
    shell.preview_button.click()
    assert len(selected) == count
    assert 'active font changed' in value(shell.status, 'text')
    assert shell.children[0].tab.open() is False
    assert opened == []
    active[0] = SimpleNamespace(id=1)
    assert shell.children[0].tab.open() is True
    assert opened == [1]


def test_preview_failure_on_tab_switch_is_contained(studio_qt):
    from fontlabapp.studios.proof_studio.practical import show_context
    from fontlabapp.qt.properties import value
    from PythonQt import QtGui

    preview = QtGui.QWidget()
    preview.set_text = lambda text: None
    shell = show_context(font=lambda: object(), selection=lambda: ('A',),
                         preview=lambda shell, studio: preview, package=lambda: None)
    studio_qt.owned.append(shell)

    def fail(text):
        raise RuntimeError('preview failed')

    preview.set_text = fail
    shell.tabs.setCurrentIndex(1)
    assert value(shell.status, 'text') == 'Preview unavailable: preview failed'


def test_failed_tab_construction_closes_partial_owner(studio_qt, monkeypatch):
    from fontlabapp.studios.proof_studio.practical import _builder, context_generators
    from importlib import import_module
    tabs = import_module("fontlabapp.studios.proof_studio.tabs")
    from fontlabapp.fontui.lifecycle import Owned

    shell = studio_qt.modules.appshell.AppShell('Test', package=lambda: None)
    studio_qt.owned.append(shell)
    closed, children = [], []
    close = Owned.close

    def recorded_close(owner):
        closed.append(owner)
        return close(owner)

    def fail(*args, **kwargs):
        from PythonQt import QtGui
        children.append(QtGui.QWidget(kwargs['parent']))
        raise RuntimeError('construction failed')

    monkeypatch.setattr(Owned, 'close', recorded_close)
    monkeypatch.setattr(tabs, 'GeneratorTab', fail)
    with pytest.raises(RuntimeError, match='construction failed'):
        _builder(context_generators()[0])(shell)
    assert len(closed) == 1
    assert closed[0]._close_complete
    assert children[0].parent() is closed[0].widget
