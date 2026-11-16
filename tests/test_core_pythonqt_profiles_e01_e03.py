# this_file: tests/test_core_pythonqt_profiles_e01_e03.py
"""Lab profiles retain the original constructor arguments and local algorithms."""
import importlib
import sys
from types import ModuleType

import pytest

ROOT = 'fontlabapp.fontui.core_pythonqt_labs.profiles'


def test_registry_when_built_then_every_original_profile_has_its_own_constructor(monkeypatch):
    registry = importlib.import_module(ROOT + '.e01_e03')
    calls = []
    actions = importlib.import_module(ROOT + '.e01_e03_actions')
    monkeypatch.setattr(actions, 'bind_tree', lambda child: child)
    lists = importlib.import_module(ROOT + '.lesson_lists')
    monkeypatch.setattr(lists, 'configure', lambda child, name: child)
    def kind(*args, **kwargs):
        calls.append((args, kwargs))
        class Built(str):
            def size(self):
                return 'measured-size'
            def setMinimumSize(self, size):
                assert size == 'measured-size'
        return Built('built')
    def module(name, **attrs):
        made = ModuleType(name)
        made.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, made)
    module('fontlabapp.glyphs.catalog.native', capture='catalog')
    module('fontlabapp.glyphs.tree.model', capture='tree')
    module('fontlabapp.qt.tables.filter.ui', FilterTableDialog=kind)
    module('fontlabapp.glyphs.tree.ui', GlyphTreeDialog=kind)
    module('fontlabapp.glyphs.tree.editable.ui', EditableGlyphTreeDialog=kind)
    lesson_ids = []
    def lesson(name):
        lesson_ids.append(name)
        return kind
    module('fontlab_python_lessons.ui', dialog_type=lesson)
    module('fontlabapp.glyphs.pattern', _capture='pattern')
    module('fontlabapp.qt.regexp.ui', panel_type=lambda *args: kind)
    from types import SimpleNamespace
    import fontlabapp
    monkeypatch.setattr(fontlabapp, '_native', lambda name: SimpleNamespace(QtCore='core', QtGui='gui'))
    for domain, capture in [('proof.numeric', 'launcher'), ('metrics.offset', 'capture'), ('metrics.worksheet', 'capture')]:
        module('fontlabapp.' + domain + '.ui', panel_type=lambda *args: kind)
        module('fontlabapp.' + domain + '.' + capture, capture=domain)
    for name in ('expandable_search', 'units_calculator'):
        module(ROOT + '.' + name, build=kind)
    for lab, profiles in registry.PROFILES.items():
        assert lab in ('E01', 'E02', 'E03')
        assert len({title for title, _ in profiles}) == len(profiles)
        for title, build in profiles:
            assert build('parent') == 'built'
    assert len(calls) == 20
    assert [call[1].get('official') for call in calls[1:5]] == [False, False, True, True]
    assert calls[7][0][-1] is False and calls[8][0][-1] is True
    assert calls[9][1]['official'] is True and calls[10][1]['official'] is False
    assert [call[0][4] for call in calls[1:5]] == [False, True, True, False]
    assert [call[1]['part'] for call in calls[13:17]] == [2, 3, 2, 3]
    assert [call[1]['official'] for call in calls[18:20]] == [False, True]
    assert lesson_ids == ['glyph-name-filter', 'glyph-metrics-model', 'glyph-metrics-form']
    assert calls[6][0] == ('parent', 'pattern')
    assert [call[0][1] for call in calls[13:17]] == ['proof.numeric', 'proof.numeric', 'metrics.offset', 'metrics.offset']


def test_construct_when_called_then_uses_lazy_module_symbol(monkeypatch):
    registry = importlib.import_module(ROOT + '.e01_e03')
    module = ModuleType('lab_fake')
    module.Kind = lambda *args, **kwargs: (args, kwargs)
    monkeypatch.setitem(sys.modules, 'lab_fake', module)
    assert registry._construct('lab_fake', 'Kind', 'parent', 4, official=True) == (('parent', 4), {'official': True})


def test_search_when_options_change_then_exact_order_and_case_preserved():
    search = importlib.import_module(ROOT + '.expandable_search').search
    assert search(('a', 'A', 'a.alt'), 'a', False, False, True) == ('a.alt', 'A', 'a')
    assert search(('a', 'A', 'a.alt'), 'a', True, True, False) == ('a',)
    with pytest.raises(ValueError):
        search(('A',), '', False, False, False)


def test_calculator_when_valid_or_invalid_then_preserves_units_and_refusals():
    calculate = importlib.import_module(ROOT + '.units_calculator').calculate
    assert calculate(500, '+', 20, 1000, 12) == (520, .52, 6.24)
    for args in [(1, '/', 0, 1000, 12), (1, '?', 1, 1000, 12), (1, '+', 1, 0, 12), (float('inf'), '+', 1, 1000, 12), (1e308, '*', 1e308, 1000, 12)]:
        with pytest.raises(ValueError):
            calculate(*args)

from _studio_qt import studio_qt  # noqa: E402,F401


@pytest.fixture
def embedded(studio_qt, monkeypatch):  # noqa: F811
    from types import SimpleNamespace
    import fontlabapp
    import fontlabapp.core.scripting as scripting
    from PythonQt import QtGui
    qt = SimpleNamespace(QtGui=QtGui, QtCore=studio_qt.QtCore)
    class CheckBox(QtGui.QCheckBox):
        checked = property(QtGui.QCheckBox.isChecked)
    monkeypatch.setattr(QtGui, 'QCheckBox', CheckBox)

    class Panel(QtGui.QDialog):
        def __init__(self, parent, title, key):
            super().__init__(parent)
            self.root = QtGui.QVBoxLayout(self)
            self.subtitle = QtGui.QLabel(self)
            self.root.addWidget(self.subtitle)
        def _connect(self, signal, callback):
            signal.connect(callback)

    monkeypatch.setattr(fontlabapp, '_native', lambda name: qt)
    monkeypatch.setattr(scripting, 'names_dialog_type', lambda: Panel)
    monkeypatch.setattr(scripting, 'show_script_dialog', lambda factory, key: factory(None))
    package = SimpleNamespace(id=9, upm=1000)
    monkeypatch.setattr(scripting, 'current_package', lambda *args: package)
    return scripting, package


def test_calculator_when_embedded_then_results_and_text_failures_are_visible(embedded, monkeypatch):
    module = importlib.import_module(ROOT + '.units_calculator')
    scripting, package = embedded
    panel = module.main()
    panel.preview_button.click()
    assert 'Units: 520' in panel.output.toPlainText()
    panel.operation.setCurrentIndex(3)
    panel.operand.setValue(0)
    panel.preview()
    assert panel.output.toPlainText() == ''
    assert 'division by zero' in panel.status.text()
    panel._capture = lambda *args: None
    panel.preview()
    assert 'Open a font' in panel.status.text()
    panel._capture = lambda *args: None if args else package
    panel.operation.setCurrentIndex(0)
    panel.preview()
    assert 'Font or UPM changed' in panel.status.text()
    for text in ['a\x00b', 'a\r', '\u2029']:
        with pytest.raises(ValueError, match='characters'):
            panel.publish(text)
    monkeypatch.setattr(panel.output, 'toPlainText', lambda: 'changed')
    with pytest.raises(ValueError, match='Qt changed'):
        panel.publish('exact')
    panel.close_button.click()


def test_search_when_embedded_then_options_results_and_failures_are_visible(embedded, monkeypatch):
    from PythonQt import QtGui
    module = importlib.import_module(ROOT + '.expandable_search')
    monkeypatch.setattr(module, 'glyph_rows', lambda: (('a', (65,)), ('a.alt', ())))
    panel = module.main()
    extra = QtGui.QPlainTextEdit()
    panel.extra_outputs.append(extra)
    assert panel.preview() and panel.output.toPlainText() == 'a\na.alt'
    panel.query.setText('absent')
    assert panel.preview() and panel.output.toPlainText() == 'No matching names.'
    panel.query.setText('')
    extra.setPlainText('old')
    assert not panel.preview() and extra.toPlainText() == ''
    buttons = panel.findChildren(QtGui.QPushButton)
    next(button for button in buttons if button.text() == 'More Options').click()
    assert not panel.options.isHidden()
    next(button for button in buttons if button.text() == 'Preview / Refresh').click()
    next(button for button in buttons if button.text() == 'Close').click()


def test_search_capture_when_unicode_and_deadline_change_then_refuses_partial(monkeypatch):
    from types import SimpleNamespace
    module = importlib.import_module(ROOT + '.expandable_search')
    import fontlabapp.glyphs.catalog.model as catalog
    monkeypatch.setattr(catalog, 'capture', lambda **kwargs: SimpleNamespace(rows=(('A', 'U+0041 U+1F600', ''),)))
    monkeypatch.setattr(module, 'monotonic', lambda: 0)
    assert module.glyph_rows() == (('A', (65, 128512)),)
    monkeypatch.setattr(catalog, 'capture', lambda **kwargs: SimpleNamespace(rows=(('A', 'U+D800', ''),)))
    with pytest.raises(ValueError, match='scalar'):
        module.glyph_rows()
    monkeypatch.setattr(catalog, 'capture', lambda **kwargs: SimpleNamespace(rows=(('A', '', ''),)))
    for times in [(0, 3), (0, 0, 3)]:
        sequence = iter(times)
        monkeypatch.setattr(module, 'monotonic', lambda: next(sequence))
        with pytest.raises(TimeoutError):
            module.glyph_rows()
