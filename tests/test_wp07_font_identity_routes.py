# this_file: tests/test_wp07_font_identity_routes.py
"""WP07 preserves complete identity and encoding actions under studio routes."""

import ast
from pathlib import Path

import pytest

STUDIOS = Path(__file__).parents[1] / 'src/fontlabapp/fonts/identity_tools'
ROUTES = {
    'font_identity/version': ('bumped', 'version_plan', 'run', 'Dialog'),
    'font_identity/names': ('validate_names', 'run', 'Dialog'),
    'font_identity/trial': ('make_trial', 'preview', 'scan_exports', 'panel_type'),
    'encoding_order/order': ('glyph_records', 'script_group', 'run', 'Dialog'),
    'encoding_order/paste': ('insert_names', 'encoding_rows', 'save_encoding', 'panel_type'),
    'encoding_order/ranges': ('glyph_records', 'coverage', 'run', 'Dialog'),
}


@pytest.mark.parametrize('route,required', ROUTES.items())
def test_route_when_migrated_then_original_actions_remain(route, required):
    path = STUDIOS / (route + '.py')
    tree = ast.parse(path.read_text(), feature_version=(3, 11))
    names = {node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    assert set(required) <= names
    imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
    assert not any((getattr(node, 'module', '') or '').startswith('fly') for node in imports)
    assert path.read_text().startswith('# this_file: src/fontlabapp/fonts/identity_tools/' + route + '.py\n')


@pytest.mark.parametrize('package,title,tabs,preview', [
    ('font_identity', 'Font Identity', ('Names and Credits', 'Bump Font Version', 'Trial Font Maker'), None),
    ('encoding_order', 'Encoding and Order', ('Glyph Order Preview and Export', 'Paste Glyph Order Encoding', 'Unicode Ranges and Codepages'), 'tmetrics'),
])
def test_studio_when_opened_then_complete_routes_and_source_tab(monkeypatch, package, title, tabs, preview):
    import importlib
    from types import SimpleNamespace

    from fontlabapp import studios

    captured = {}

    def opened(label, routes, **kwargs):
        captured.update(title=label, routes=routes, **kwargs)
        return captured

    def route(label, builder, **kwargs):
        return SimpleNamespace(title=label, build=builder, **kwargs)

    import fontlabapp.fontui as fontui  # noqa: PLR0402 - avoid root lazy native exports

    monkeypatch.setattr(fontui, 'identity_studio', opened, raising=False)
    monkeypatch.setattr(fontui, 'identity_route', route, raising=False)
    monkeypatch.setattr(fontui, 'identity_panel', lambda path, name, parent, **kw: parent, raising=False)
    studio = importlib.import_module('fontlabapp.studios.' + package)
    sentinel = object()
    assert studio.show(parent=sentinel, package=sentinel, font=sentinel, tab=tabs[-1]) is captured
    assert captured['title'] == title
    assert tuple(item.title for item in captured['routes']) == tabs
    assert captured.get('preview') == preview
    assert captured['tab'] == tabs[-1]
    assert captured['package'] is captured['font'] is captured['parent'] is sentinel
    assert all(item.build(sentinel) is sentinel for item in captured['routes'])
    assert getattr(studios, package) is studio


@pytest.fixture
def source_modules(monkeypatch):
    import importlib
    import sys
    from types import SimpleNamespace

    import fontlabapp
    from fontlabapp.core import scripting

    monkeypatch.setattr(fontlabapp, '_native', lambda name: SimpleNamespace(QtCore=None, QtGui=None))
    monkeypatch.setitem(vars(fontlabapp), 'fontlab', SimpleNamespace())
    monkeypatch.setattr(scripting, 'font_info_dialog_type', lambda: object)
    loaded = []

    def load(route, base=object):
        monkeypatch.setattr(scripting, "font_info_dialog_type", lambda: base)
        name = 'fontlabapp.fonts.identity_tools.' + route.replace('/', '.')
        monkeypatch.delitem(sys.modules, name, raising=False)
        module = importlib.import_module(name)
        loaded.append(name)
        return module

    yield load
    for name in loaded:
        sys.modules.pop(name, None)


def test_identity_plans_when_versions_and_names_then_original_validation(source_modules):
    from types import SimpleNamespace

    version = source_modules('font_identity/version')
    assert version.bumped(1, 999, 'minor') == (2, 0)
    assert version.bumped(2, 50, 'major') == (3, 0)
    for args in [(0, -1, 'minor'), (65535, 999, 'minor'), (1, 0, 'x'), ('1', 0, 'minor')]:
        with pytest.raises(ValueError):
            version.bumped(*args)
    info = SimpleNamespace(versionMajor=1, versionMinor=2, openTypeNameVersion='Version 1.002')
    package = SimpleNamespace(versionMajor=1, versionMinor=2, info=info)
    assert version.version_plan(package, 'minor', False, '2026-11-11') == [
        (None, 'versionMajor', 1, 1), (None, 'versionMinor', 2, 3),
        (None, 'openTypeNameVersion', 'Version 1.002', 'Version 1.003')]
    names = source_modules('font_identity/names')
    valid = {'familyName': 'Family', 'styleName': 'Regular', 'openTypeNameVersion': 'Version 1.003'}
    assert names.validate_names(valid) is valid
    for key, value in [('familyName', ''), ('styleName', '\n'), ('openTypeNameVersion', '1.003')]:
        with pytest.raises(ValueError):
            names.validate_names({**valid, key: value})
    with pytest.raises(ValueError, match='control'):
        names.validate_names({**valid, 'copyright': '\n'})


def test_order_and_ranges_when_secondary_encodings_then_preserved(source_modules):
    order = source_modules('encoding_order/order')
    records = [('B', [66, 0x10400]), ('.notdef', []), ('A', [65]), ('z', [])]
    for mode in ('Name', 'Unicode', 'Script'):
        assert order.sorted_order(records, mode)[0][0] == '.notdef'
    assert order.run(records, 'Unicode') == '.notdef\nA\nB\nz\n'
    assert order.run([], 'Name') == ''
    assert order.script_group([]) == 'Unencoded'
    assert order.script_group([-1]) == 'Unknown'
    assert order.script_group([0x410]) == 'Cyrillic'
    ranges = source_modules('encoding_order/ranges')
    bits, rows = ranges.run(records)
    assert 0 in bits and 57 in bits
    assert any(row[-1] == 'Multibyte: review manually' for row in rows)
    full = set()
    for _, codec in ranges.CODEPAGES[:10]:
        for byte in range(32, 256):
            try:
                full.add(ord(bytes([byte]).decode(codec)))
            except UnicodeDecodeError:
                pass
    assert any(row[-1] == 'Complete printable coverage' for row in ranges.coverage(full)[1])


def test_encoding_when_inserted_then_complete_exclusive_file(source_modules, tmp_path):
    paste = source_modules('encoding_order/paste')
    names, unknown = paste.insert_names(('A', 'B', 'C', 'D'), 'D D missing B', 'C')
    assert names == ('A', 'D', 'B', 'C') and unknown == ('missing',)
    for text in ('\u2029', 'missing'):
        with pytest.raises(ValueError):
            paste.insert_names(('A',), text, 'A')
    with pytest.raises(ValueError):
        paste.insert_names((), 'A', 'A')
    path = tmp_path / 'new.enc'
    assert paste.save_encoding(path, names) == ()
    assert path.read_text().endswith('A\nD\nB\nC\n')
    with pytest.raises(FileExistsError):
        paste.save_encoding(path, names)
    assert paste.encoding_rows(('A', 'é', '%invalid', '', 'A B')) == (('A',), ('é', '%invalid', '', 'A B'))
    for bad in ((), ('A', 'A')):
        with pytest.raises(ValueError):
            paste.encoding_rows(bad)
    for bad in ('bad.txt', 'bad\u2029.enc'):
        with pytest.raises(ValueError):
            paste.save_encoding(tmp_path / bad, names)
    with pytest.raises(ValueError):
        paste.save_encoding(tmp_path / 'unsupported.enc', ('é',))


@pytest.mark.parametrize('route', ('font_identity/version', 'font_identity/names', 'encoding_order/order', 'encoding_order/ranges'))
def test_rows_when_refilled_then_numeric_sort_and_keyboard_selection(source_modules, route):
    from types import SimpleNamespace

    calls, data = [], {}

    class Base:
        def rows(self, headings, rows):
            calls.append(('fill', headings, rows))

    module = source_modules(route, base=Base)
    module.QtGui = SimpleNamespace(QHeaderView=SimpleNamespace(Interactive=1),
                                   QAbstractItemView=SimpleNamespace(SelectRows=2, SingleSelection=3))
    module.QtCore = SimpleNamespace(Qt=SimpleNamespace(EditRole=4, StrongFocus=5))
    panel = object.__new__(module.panel_type())
    panel.table = SimpleNamespace(
        setSortingEnabled=lambda enabled: calls.append(('sorting', enabled)),
        horizontalHeader=lambda: SimpleNamespace(setSectionResizeMode=lambda mode: calls.append(('width', mode))),
        setSelectionBehavior=lambda mode: calls.append(('selection', mode)),
        setSelectionMode=lambda mode: calls.append(('mode', mode)),
        setFocusPolicy=lambda mode: calls.append(('focus', mode)),
        item=lambda row, column: SimpleNamespace(setData=lambda role, value: data.update({(row, column): (role, value)})),
    )
    panel.rows(['Name', 'Index'], [('A', 100), ('B', 2)])
    assert calls[0] == ('sorting', False) and calls[-1] == ('sorting', True)
    assert data == {(0, 1): (4, 100), (1, 1): (4, 2)}
    assert ('width', 1) in calls and ('focus', 5) in calls


def test_trial_table_when_refreshed_then_rows_sort_without_affecting_write_order(source_modules, monkeypatch):
    from types import SimpleNamespace

    import fontlabapp

    trial = source_modules('font_identity/trial')
    calls = []

    class Base:
        def refresh(self):
            calls.append('fill')

    monkeypatch.setattr(trial, 'panel_type', lambda: Base)
    gui = SimpleNamespace(QHeaderView=SimpleNamespace(Interactive=1),
                          QAbstractItemView=SimpleNamespace(SelectRows=2, SingleSelection=3))
    monkeypatch.setattr(fontlabapp, '_native', lambda name: SimpleNamespace(QtGui=gui, QtCore=SimpleNamespace(Qt=SimpleNamespace(StrongFocus=4))))
    panel = object.__new__(trial.studio_panel_type())
    panel.table = SimpleNamespace(
        setSortingEnabled=lambda enabled: calls.append(enabled),
        horizontalHeader=lambda: SimpleNamespace(setSectionResizeMode=lambda mode: None),
        setSelectionBehavior=lambda mode: None,
        setSelectionMode=lambda mode: None,
        setFocusPolicy=lambda mode: None,
    )
    panel.refresh()
    assert calls == [False, 'fill', True]
