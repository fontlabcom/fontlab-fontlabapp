# this_file: tests/test_studio_labs_e04_e06.py
"""The calendar, completion and drag profiles retain distinct callable routes."""
from importlib import import_module
from types import SimpleNamespace
import sys

import pytest

BASE = 'fontlabapp.fontui.core_pythonqt_labs.profiles.'


def test_profile_counts_and_distinct_titles():
    module = import_module(BASE + 'e04_e06')
    assert {key: len(rows) for key, rows in module.PROFILES.items()} == {'E04': 3, 'E05': 2, 'E06': 6}
    for rows in module.PROFILES.values():
        assert len({title for title, build in rows}) == len(rows)
        assert all(callable(build) for title, build in rows)


@pytest.mark.parametrize('lab,index,official', [('E04', 0, False), ('E04', 1, True), ('E05', 0, False), ('E05', 1, True)])
def test_existing_profile_constructs_original_dialog(monkeypatch, lab, index, official):
    module = import_module(BASE + 'e04_e06')
    target = 'calendar' if lab == 'E04' else 'completion'
    klass = 'GlyphCalendarDialog' if lab == 'E04' else 'GlyphCompletionDialog'
    calls = []
    ui = SimpleNamespace(**{klass: lambda parent, capture, **kw: calls.append((parent, capture, kw)) or 'panel'})
    def capture():
        return None
    monkeypatch.setitem(sys.modules, 'fontlabapp.glyphs.' + target + '.ui', ui)
    monkeypatch.setitem(sys.modules, 'fontlabapp.glyphs.catalog.native', SimpleNamespace(capture=capture))
    assert module.PROFILES[lab][index][1]('parent') == 'panel'
    assert calls == [('parent', capture, {'official': official})]


@pytest.mark.parametrize('index,name', tuple(enumerate(('deferred_glyph_report', 'draggable_glyph_names', 'font_drop_inspector', 'font_file_drop_shelf', 'glyph_pair_board', 'proof_word_magnets'))))
def test_drop_profile_constructs_original_panel(monkeypatch, index, name):
    module = import_module(BASE + 'e04_e06')
    calls = []
    qt, capture, opener = object(), object(), object()
    panel = SimpleNamespace(panel_type=lambda binding, source: lambda parent: calls.append((binding, source, parent)) or 'panel', open_in_fontlab=opener)
    monkeypatch.setitem(sys.modules, 'PythonQt', qt)
    monkeypatch.setitem(sys.modules, BASE + name, panel)
    monkeypatch.setitem(sys.modules, 'fontlabapp.glyphs.character_map.capture', SimpleNamespace(capture=capture))
    assert module.PROFILES['E06'][index][1]('parent') == 'panel'
    assert calls == [(qt, opener if index == 3 else capture, 'parent')]


def test_calendar_proof_profile_embeds_without_show(monkeypatch):
    module = import_module(BASE + 'e04_e06')
    qt, calls = object(), []
    monkeypatch.setitem(sys.modules, 'PythonQt', qt)
    monkeypatch.setitem(sys.modules, BASE + 'calendar_proof', SimpleNamespace(show=lambda *args, **kw: calls.append((args, kw)) or 'panel'))
    assert module.PROFILES['E04'][2][1]('parent') == 'panel'
    assert calls == [((qt, 'parent'), {'embedded': True})]


@pytest.fixture
def real_qt(monkeypatch):
    """Exercise production builders with Qt widgets, using native property spelling."""
    from PySide6 import QtCore, QtGui, QtWidgets
    from fontlabapp.qt.tables.filter.model import Table

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    class Dialog(QtWidgets.QDialog):
        palette = property(QtWidgets.QDialog.palette)

    class Label(QtWidgets.QLabel):
        font = property(QtWidgets.QLabel.font)

    gui = SimpleNamespace(**{name: getattr(QtGui, name) for name in dir(QtGui) if name.startswith('Q')})
    gui.__dict__.update({name: getattr(QtWidgets, name) for name in dir(QtWidgets) if name.startswith('Q')})
    class PlainTextEdit(QtWidgets.QPlainTextEdit):
        plainText = property(QtWidgets.QPlainTextEdit.toPlainText)

    class TextEdit(QtWidgets.QTextEdit):
        plainText = property(QtWidgets.QTextEdit.toPlainText)

    gui.QDialog, gui.QLabel = Dialog, Label
    gui.QPlainTextEdit, gui.QTextEdit = PlainTextEdit, TextEdit
    gui.QStringListModel, gui.QSortFilterProxyModel = QtCore.QStringListModel, QtCore.QSortFilterProxyModel
    qt = SimpleNamespace(QtGui=gui, QtCore=QtCore)
    monkeypatch.setitem(sys.modules, 'PythonQt', qt)
    for name in ('fontlabapp.glyphs.names.ui', 'fontlabapp.glyphs.calendar.ui', 'fontlabapp.glyphs.completion.ui'):
        monkeypatch.delitem(sys.modules, name, raising=False)
    rows = Table(('Name', 'Unicode', 'Modified'), (('A', 'U+0041', '2026-11-11 12:00:00'), ('V', 'U+0056', '')))
    monkeypatch.setitem(sys.modules, 'fontlabapp.glyphs.catalog.native', SimpleNamespace(capture=lambda **kw: rows))
    facts = SimpleNamespace(context=(1, 7, 'Regular'), rows=(SimpleNamespace(name='A', unicodes=(65,)), SimpleNamespace(name='V', unicodes=(86,))))
    monkeypatch.setitem(sys.modules, 'fontlabapp.glyphs.character_map.capture', SimpleNamespace(capture=lambda: facts))
    completion_ui = import_module('fontlabapp.glyphs.completion.ui')
    monkeypatch.setattr(completion_ui, '_string_boundary', (completion_ui._connect_string, completion_ui._disconnect_string), raising=False)
    monkeypatch.setattr(completion_ui, '_connect_string', lambda sender, slot: sender.activated[str].connect(slot))
    monkeypatch.setattr(completion_ui, '_disconnect_string', lambda sender, slot: sender.activated[str].disconnect(slot))
    yield qt, app
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


@pytest.mark.parametrize('lab,index', [(lab, i) for lab, count in (('E04', 3), ('E05', 2), ('E06', 6)) for i in range(count)])
def test_real_profile_constructs_embeds_and_closes(real_qt, lab, index):
    qt, app = real_qt
    module = import_module(BASE + 'e04_e06')
    title, build = module.PROFILES[lab][index]
    parent = qt.QtGui.QWidget()
    panel = build(parent)
    panel.setWindowFlags(qt.QtCore.Qt.Widget)
    assert panel.parent() is parent
    assert not panel.isWindow()
    if lab == 'E04' and index < 2:
        assert panel._snapshot.rows[0][0] == 'A'
        panel.controls.calendar.setSelectedDate(qt.QtCore.QDate(2026, 11, 11))
        assert 'A — U+0041' in panel.output.toPlainText()
    elif lab == 'E04':
        assert panel.editor.isReadOnly() and not panel.isVisible()
    elif lab == 'E05':
        assert panel.words == ('A', 'V')
        panel.controls.widget.setPlainText('😀 draft')
        panel.refresh()
        assert panel.controls.widget.toPlainText() == '😀 draft'
    elif index != 3:
        assert panel.facts.rows[0].name == 'A'
    assert panel.close() is True, title
    parent.deleteLater()


@pytest.mark.parametrize('lab,index', [(lab, i) for lab, count in (('E04', 3), ('E05', 2), ('E06', 6)) for i in range(count)])
def test_real_profile_actions_publish_profile_data_and_preserve_drafts(real_qt, lab, index):
    qt, app = real_qt
    module = import_module(BASE + 'e04_e06')
    title, build = module.PROFILES[lab][index]
    panel = build(None)
    published = []
    actions = module.bindings(panel, title, published.append)
    if lab == 'E04' and index < 2:
        panel.controls.calendar.setSelectedDate(qt.QtCore.QDate(2026, 11, 11))
        actions['preview']()
        assert published == [('A',)]
    elif lab == 'E04':
        panel.editor.setPlainText('2026 11')
        actions['preview']()
        assert published == ['2026 11']
    elif lab == 'E05':
        panel.controls.widget.setPlainText('AV😀')
        actions['preview']()
        actions['refresh']()
        assert published == ['AV😀']
        assert panel.controls.widget.toPlainText() == 'AV😀'
    elif index == 3:
        assert actions == {}, 'Opening files stays an explicit labelled original action.'
    elif index == 0:
        actions['preview']()
        assert published == [('A', 'V')]
    elif index in (1, 2):
        panel.entry.setText('AV')
        assert actions['dirty']()
        if index == 2:
            panel.use_input()
        actions['preview']()
        assert published == (['/A/V'] if index == 1 else ['AV'])
        panel.entry.clear()
        assert not actions['dirty']()
    else:
        assert not actions['dirty']()
        panel.entry.setText('/A/V' if index == 4 else 'AV test')
        assert actions['dirty']()
        panel.use_input()
        assert actions['dirty'](), 'Refresh must refuse to discard staged rows.'
        actions['preview']()
        assert published == (['/A/V'] if index == 4 else ['AV test'])
        panel.clear()
        assert not actions['dirty']()
    panel.close()


def test_inspector_preview_handles_native_text_property_and_clear(real_qt):
    module = import_module(BASE + 'e04_e06')
    title, build = module.PROFILES['E06'][2]
    panel = build(None)
    published = []
    actions = module.bindings(panel, title, published.append)
    panel.receive(SimpleNamespace(formats=lambda: ['text/plain'], hasUrls=lambda: False,
                                  hasText=lambda: True, text='A😀'))
    actions['preview']()
    assert published == ['A😀']
    panel.clear()
    actions['preview']()
    assert published[-1] == ''
    panel.receive(SimpleNamespace(formats=lambda: ['application/binary'], hasUrls=lambda: False,
                                  hasText=lambda: False))
    assert panel.proof_text == ''
    panel.proof_text = 'old'
    panel.invalidate()
    assert panel.proof_text == ''
    panel.close()


@pytest.mark.parametrize('index', [0, 1, 2, 4, 5])
def test_drop_refresh_uses_fenced_capture_seam_and_invalidates_on_refusal(real_qt, index):
    module = import_module(BASE + 'e04_e06')
    title, build = module.PROFILES['E06'][index]
    panel = build(None)

    def refuse():
        raise ValueError('Captured font changed')

    panel._capture = refuse
    panel.refresh()
    assert panel.facts is None
    assert 'Captured font changed' in panel.status.text()
    panel.close()


@pytest.mark.parametrize('name', ['draggable_glyph_names', 'glyph_pair_board', 'proof_word_magnets'])
def test_drop_error_and_close_refusal_paths(real_qt, monkeypatch, name):
    qt, app = real_qt
    module = import_module(BASE + name)
    facts = SimpleNamespace(rows=(SimpleNamespace(name='A', unicodes=(65,)), SimpleNamespace(name='V', unicodes=(86,))))
    panel = module.panel_type(qt, lambda: facts)()
    panel.output.clear()
    with pytest.raises(ValueError, match='no output'):
        panel.copy_output()
    panel.output.setPlainText('AV')
    panel.copy_output()
    assert qt.QtGui.QApplication.clipboard().text() == 'AV'
    panel.export.origin = None
    panel.export.mouseMoveEvent(SimpleNamespace(buttons=lambda: qt.QtCore.Qt.NoButton))
    if name != 'draggable_glyph_names':
        with pytest.raises(ValueError, match='Select rows'):
            panel.remove_selected()
        with pytest.raises(ValueError, match='Drop'):
            panel.receive(SimpleNamespace(hasText=lambda: False))
        with pytest.raises(ValueError, match='Add'):
            panel.output_mime()
    with monkeypatch.context() as context:
        context.setattr(panel.terminal, 'finish', lambda **kw: False)
        assert not panel.dispose()
    monkeypatch.setattr(sys, '_fontlab_samples', {module.KEY: panel}, raising=False)
    assert panel.dispose()
    assert module.KEY not in sys._fontlab_samples
    panel.close()


@pytest.mark.parametrize('name', ['glyph_pair_board', 'proof_word_magnets'])
def test_drop_routes_native_reorder_and_external_mime_separately(real_qt, monkeypatch, name):
    qt, app = real_qt
    original_list = qt.QtGui.QListWidget
    calls = []

    class List(original_list):
        def dragEnterEvent(self, event):
            calls.append('native enter')

        def dragMoveEvent(self, event):
            calls.append('native move')

        def dropEvent(self, event):
            calls.append('native drop')

        def startDrag(self, actions):
            calls.append('native drag')

    monkeypatch.setattr(qt.QtGui, 'QListWidget', List)
    module = import_module(BASE + name)
    facts = SimpleNamespace(rows=(SimpleNamespace(name='A', unicodes=(65,)), SimpleNamespace(name='V', unicodes=(86,))))
    panel = module.panel_type(qt, lambda: facts)()
    event = SimpleNamespace(source=lambda: panel.items)
    panel.items.dragEnterEvent(event)
    panel.items.dragMoveEvent(event)
    panel.items.dropEvent(event)
    panel.items.startDrag(qt.QtCore.Qt.MoveAction)
    assert calls == ['native enter', 'native move', 'native drop', 'native drag']
    assert not panel.busy
    mime = SimpleNamespace(hasText=lambda: False, hasUrls=lambda: False)
    event = SimpleNamespace(source=lambda: None, mimeData=lambda: mime,
                            accept=lambda: calls.append('accepted'), ignore=lambda: calls.append('ignored'),
                            setDropAction=lambda action: calls.append(action))
    panel.items.dragEnterEvent(event)
    assert calls[-1] == 'ignored'
    mime.hasText = lambda: True
    panel.items.dragMoveEvent(event)
    assert calls[-1] == 'accepted'
    with monkeypatch.context() as context:
        context.setattr(module, 'REORDER', False)
        other = module.panel_type(qt, lambda: facts)()
        context.setattr(other, 'drag_selected', lambda: calls.append('export'))
        other.items.startDrag(qt.QtCore.Qt.CopyAction)
        assert calls[-1] == 'export'
        other.close()
    panel.close()


def test_calendar_proof_export_draft_and_exact_text_paths(real_qt, tmp_path, monkeypatch):
    qt, app = real_qt
    module = import_module(BASE + 'calendar_proof')
    panel = module.show(qt, None, embedded=True)
    with pytest.raises(ValueError, match='Build a proof'):
        panel.payload()
    panel._capture = lambda: frozenset(range(128))
    for button in panel.findChildren(qt.QtGui.QPushButton):
        if button.text() == 'Build':
            button.click()
    assert panel.proof_html and panel.editor.toPlainText()
    target = tmp_path / 'proof.html'
    panel.destination.setText(str(target))
    panel.after_save = lambda: panel.status.setText('hook')
    panel.edited()
    assert panel.close() is False
    panel.save()
    assert target.read_text() == panel.proof_html and not panel.dirty
    panel.highlighter = SimpleNamespace(setDocument=lambda document: None)
    panel.close()
    panel.wire(SimpleNamespace(connect=lambda callback: callback()), lambda: pytest.fail('Closed callback ran'))

    class Normalising:
        text = 'old'
        def toPlainText(self):
            return self.text
        def setPlainText(self, text):
            self.text = text if text == 'old' else 'changed'

    editor = Normalising()
    with pytest.raises(ValueError, match='normalization'):
        module.set_plain_exact(editor, 'new')
    assert editor.text == 'old'


@pytest.mark.parametrize('name', ['draggable_glyph_names', 'font_drop_inspector', 'font_file_drop_shelf'])
def test_report_lists_sort_both_ways_keep_selected_identity_and_resize(real_qt, tmp_path, name):
    qt, app = real_qt
    module = import_module(BASE + name)
    opened = []
    facts = SimpleNamespace(rows=(SimpleNamespace(name='V', unicodes=(86,)), SimpleNamespace(name='A', unicodes=(65,))))
    panel = module.panel_type(qt, opened.append if name == 'font_file_drop_shelf' else lambda: facts)()
    if name == 'font_file_drop_shelf':
        paths = [tmp_path / 'Z.ttf', tmp_path / 'A.ttf']
        for path in paths:
            path.write_bytes(b'font fixture')
        panel.add_paths([str(path) for path in paths])
    elif name == 'font_drop_inspector':
        panel.items.addItems(['text/plain', 'application/json'])
    original = panel.items.item(0)
    original.setSelected(True)
    names = panel.text_items()
    buttons = {button.text(): button for button in panel.findChildren(qt.QtGui.QPushButton)}
    assert 'Sort A–Z' in buttons and 'Sort Z–A' in buttons
    buttons['Sort A–Z'].click()
    assert panel.text_items() == tuple(sorted(names))
    assert panel.items.selectedItems() == [original]
    buttons['Sort Z–A'].click()
    assert panel.text_items() == tuple(sorted(names, reverse=True))
    assert panel.items.selectedItems() == [original]
    if name == 'font_file_drop_shelf':
        panel.open_selected()
        assert opened == [str(paths[0])], 'Sort must preserve the selected file target.'
    elif name == 'draggable_glyph_names':
        assert panel.output.toPlainText() == ''.join(panel.text_items())
        assert panel.output_mime().text() == '/V'
    panel.show()
    app.processEvents()
    width = panel.items.width()
    panel.resize(panel.width() + 200, panel.height())
    app.processEvents()
    assert panel.items.width() > width
    panel.close()
