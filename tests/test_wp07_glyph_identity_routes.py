# this_file: tests/test_wp07_glyph_identity_routes.py
"""The consolidated identity routes retain exact legacy calculations."""
import ast
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).parents[1] / 'src/fontlabapp/studios'


def functions(studio, route, names):
    path = ROOT.parent / 'glyphs/identity_tools' / studio / (route + '.py')
    tree = ast.parse(path.read_text())
    tree.body = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    scope = {'re': re}
    exec(compile(tree, str(path), 'exec'), scope)
    return scope


def test_case_pairs_preserve_duplicate_owner_and_expanding_case_refusal():
    f = functions('character_consistency', 'case_pairs', {'swap_case', 'index', 'counterpart'})
    codes, owners = f['index']([('a', [97]), ('a.alt', [97]), ('A', [65]), ('a.sc', []), ('A.sc', [])])
    assert owners[97] == 'a'
    assert f['swap_case']('ß') == ''
    assert f['counterpart']('a.sc', codes, owners) == ('A.sc', 'via a → A')
    assert f['counterpart']('absent', codes, owners) == (None, 'unencoded')


@pytest.mark.parametrize(('name', 'find', 'replacement', 'regex', 'expected'), [
    ('a.alt', '.alt', '.ss01', False, 'a.ss01'),
    ('a.alt', '', 'b', False, 'a.alt'),
    ('uni0041', '^uni', 'u', True, 'u0041'),
])
def test_rename_preserves_literal_and_regex_rules(name, find, replacement, regex, expected):
    f = functions('glyph_identity', 'batch_rename', {'replaced'})
    assert f['replaced'](name, find, replacement, regex) == expected


def test_rename_rejects_invalid_regex():
    f = functions('glyph_identity', 'batch_rename', {'replaced'})
    with pytest.raises(re.error):
        f['replaced']('a', '[', 'b', True)


@pytest.mark.parametrize(('studio', 'title', 'preview', 'route_names'), [
    ('glyph_identity', 'Glyph Identity', 'tglyph',
     ['batch_rename', 'suffix_tool', 'unicode_from_names']),
    ('character_consistency', 'Character Consistency', 'tmetrics',
     ['case_pairs', 'character_set_compare', 'style_linker']),
])
def test_assembly_retains_all_routes_and_explicit_context(monkeypatch, studio, title, preview, route_names):
    import importlib.util
    from types import SimpleNamespace

    package = 'fontlabapp.studios.' + studio
    made = []
    captured = {}

    def panel(module, name, parent, *, factory_type=False):
        made.append((module, name, parent, factory_type))
        return object()

    def show(title, routes, **kwargs):
        captured.update(title=title, routes=routes, **kwargs)
        for route in routes:
            route.build(kwargs['parent'])
        return captured

    def route(title, build, **kwargs):
        return SimpleNamespace(title=title, build=build, **kwargs)

    import fontlabapp.fontui as fontui
    monkeypatch.setattr(fontui, 'identity_panel', panel, raising=False)
    monkeypatch.setattr(fontui, 'identity_studio', show, raising=False)
    monkeypatch.setattr(fontui, 'identity_route', route, raising=False)
    spec = importlib.util.spec_from_file_location(package + '.app', ROOT / studio / 'app.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.show(parent='parent', font='font', package='package', tab='chosen')
    assert result['title'] == title and result['preview'] == preview
    assert (result['font'], result['package'], result['tab']) == ('font', 'package', 'chosen')
    assert [item[2] for item in made] == ['parent'] * len(result['routes'])
    assert len(made) == (4 if studio == 'glyph_identity' else 3)

    expected_glyph_columns = [0, 0, 0, None] if studio == 'glyph_identity' else [0, None, None]
    assert [getattr(item, 'glyph_column', None) for item in result['routes']] == expected_glyph_columns

    if studio == 'glyph_identity':
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication, QTreeWidget, QTreeWidgetItem
        application = QApplication.instance() or QApplication([])
        tree = QTreeWidget()
        group = QTreeWidgetItem(tree, ['U+0061 two glyphs'])
        first = QTreeWidgetItem(group, ['a'])
        second = QTreeWidgetItem(group, ['a.alt'])
        target = result['routes'][-1]
        panel = SimpleNamespace(tree=tree, items={('a', 97): first, ('a.alt', 97): second})
        assert target.preview_signals == (('tree', 'itemSelectionChanged'),)
        tree.setCurrentItem(second)
        assert target.preview_target(panel) == ('a.alt', None)
        tree.setSortingEnabled(True)
        tree.sortItems(0, Qt.DescendingOrder)
        assert target.preview_target(panel) == ('a.alt', None)
        tree.setCurrentItem(group)
        assert target.preview_target(panel) is None
        tree.clearSelection()
        tree.close()
        application.processEvents()
