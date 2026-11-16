# this_file: tests/test_core_pythonqt_lab_sorting.py
"""Real Qt sorting preserves source glyph identity and pending edit targets."""
from types import SimpleNamespace as NS
import importlib
import pytest
from legacy_panel_qt import font_host as font_host

from legacy_panel_qt import legacy_qt as legacy_qt


def test_proxy_sort_keeps_source_rows_numeric_order_and_selection(legacy_qt):  # noqa: F811
    from PySide6 import QtCore, QtWidgets
    from fontlabapp.fontui.core_pythonqt_labs.profiles import table_sorting

    parent = QtWidgets.QWidget()
    legacy_qt.owned.append(parent)
    view = QtWidgets.QTableView(parent)
    panel = NS()
    model = legacy_qt.gui.QStandardItemModel(parent)
    for name, score in [('B', '10'), ('A', '2')]:
        model.appendRow([legacy_qt.gui.QStandardItem(name), legacy_qt.gui.QStandardItem(score)])
    qt = NS(QtCore=QtCore, QtGui=legacy_qt.gui)
    table_sorting.install(panel, view, model, qt, numeric=(1,))
    view.setCurrentIndex(view.model().index(0, 0))
    view.sortByColumn(0, QtCore.Qt.AscendingOrder)
    assert view.currentIndex().data() == 'B'
    assert table_sorting.source_row(panel, view.model().index(0, 0)) == 1
    view.sortByColumn(1, QtCore.Qt.AscendingOrder)
    assert view.model().index(0, 1).data() == '2'
    assert view.horizontalHeader().sectionResizeMode(0) == QtWidgets.QHeaderView.Interactive
    assert table_sorting.source_row(NS(), model.index(0, 0)) == 0




@pytest.fixture
def profile_host(legacy_qt, font_host, monkeypatch):  # noqa: F811 - fixtures
    import fly
    from PySide6 import QtCore
    qt = NS(QtCore=QtCore, QtGui=legacy_qt.gui)
    monkeypatch.setattr(fly, 'qt', qt)
    return qt, legacy_qt.owned


def make_panel(profile_host, name):
    qt, owned = profile_host
    module = importlib.import_module('fontlabapp.fontui.core_pythonqt_labs.profiles.' + name)
    if name == 'glyph_mark_colours':
        captured = (1, {'B': (2, 0), 'A': (3, 0)})
    elif name == 'glyph_review_form':
        captured = (1, {'B': (2, ''), 'A': (3, '')})
    else:
        captured = NS(rows=(('B', 'U+0042', ''), ('A', '', '')))
    panel = module.show(qt, capture=lambda: captured, embedded=True)
    owned.append(panel)
    return panel, module


@pytest.mark.parametrize('name', ['glyph_proof_worksheet', 'glyph_coverage_grid', 'glyph_encoding_chart', 'glyph_mark_colours', 'glyph_review_form', 'glyph_review_priorities'])
def test_sorted_refresh_keeps_live_selection_model(profile_host, name):
    from PySide6 import QtCore, QtWidgets
    from shiboken6 import isValid
    panel, _ = make_panel(profile_host, name)
    panel.table_view.sortByColumn(0, QtCore.Qt.AscendingOrder)
    selection = panel.table_view.selectionModel()
    panel.refresh()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert isValid(selection)
    assert panel.table_view.selectionModel() is selection
    assert panel.table_view.isSortingEnabled()
    assert panel.table_view.horizontalHeader().sectionResizeMode(0) == QtWidgets.QHeaderView.Interactive


def test_sorted_worksheet_edit_targets_source_glyph(profile_host):
    from PySide6 import QtCore
    from fontlabapp.fontui.core_pythonqt_labs.profiles.e07_e09_actions import proof_text
    panel, _ = make_panel(profile_host, 'glyph_proof_worksheet')
    panel.table_view.sortByColumn(0, QtCore.Qt.AscendingOrder)
    panel.table_view.clicked.emit(panel.table_view.model().index(0, 0))
    assert panel.current_row == 2
    panel.draft_field.setText('10')
    panel.apply_draft()
    assert panel.drafts == {'A': '10'}
    assert proof_text(panel, 'Glyph Proof Worksheet') == '/B\n' + '/A' * 10
    panel.dirty = False


def test_sorted_review_form_preview_and_write_keep_selected_glyph(profile_host, monkeypatch):
    from PySide6 import QtCore
    from fontlabapp.fontui.core_pythonqt_labs.profiles.e07_e09_actions import proof_text
    panel, module = make_panel(profile_host, 'glyph_review_form')
    panel.table_view.sortByColumn(0, QtCore.Qt.AscendingOrder)
    panel.table_view.clicked.emit(panel.table_view.model().index(0, 0))
    assert panel.current_row == 2
    assert proof_text(panel, 'Glyph Review Form') == ('A',)
    panel.note_field.setPlainText('Keep the apex')
    calls = []
    monkeypatch.setattr(module, 'apply_changes', lambda package, baseline, changes, **kwargs: calls.append(changes) or tuple(changes))
    panel.apply()
    assert list(calls[0]) == ['A']
    assert 'Keep the apex' in calls[0]['A']


def test_active_mark_editor_survives_resort_without_switching_glyph(profile_host):
    from PySide6 import QtCore
    from fontlabapp.fontui.core_pythonqt_labs.profiles.e07_e09_actions import proof_text
    panel, _ = make_panel(profile_host, 'glyph_mark_colours')
    panel.table_view.sortByColumn(0, QtCore.Qt.AscendingOrder)
    index = panel.table_view.model().index(0, 1)
    panel.table_view.setCurrentIndex(index)
    delegate = panel.editor_delegate
    editor = delegate.createEditor(panel, None, index)
    delegate.setEditorData(editor, index)
    editor.setCurrentIndex(1)
    mark = editor.itemData(1)
    panel.table_view.sortByColumn(0, QtCore.Qt.DescendingOrder)
    assert proof_text(panel, 'Glyph Mark Colours') == ('A',)
    delegate.flush()
    assert panel.changed == {'A': mark}
    delegate.setModelData(editor, panel.table_view.model(), index)
    assert panel.changed == {'A': mark}
    panel.discard_changes()
    delegate.destroyEditor(editor, index)


def test_sorted_priority_delegate_edits_and_previews_selected_source(profile_host):
    from PySide6 import QtCore, QtGui
    from fontlabapp.fontui.core_pythonqt_labs.profiles.e07_e09_actions import proof_text
    panel, _ = make_panel(profile_host, 'glyph_review_priorities')
    panel.change_cell(1, 4)
    panel.table_view.sortByColumn(0, QtCore.Qt.AscendingOrder)
    index = panel.table_view.model().index(0, 1)
    panel.table_view.setCurrentIndex(index)
    assert proof_text(panel, 'Glyph Review Priorities') == ('A',)
    event = QtGui.QKeyEvent(QtCore.QEvent.KeyPress, QtCore.Qt.Key_Delete, QtCore.Qt.NoModifier)
    delegate = panel.table_view.itemDelegateForColumn(1)
    assert delegate.editorEvent(event, panel.table_view.model(), None, index)
    assert panel.cell_value(1) == 0
    panel.dirty = False


def test_proxy_handles_pythonqt_properties_and_persistent_indexes(legacy_qt):  # noqa: F811
    from PySide6 import QtCore, QtWidgets
    from fontlabapp.fontui.core_pythonqt_labs.profiles import table_sorting
    parent = QtWidgets.QWidget()
    legacy_qt.owned.append(parent)
    view = QtWidgets.QTableView(parent)
    panel, model = NS(), legacy_qt.gui.QStandardItemModel(parent)
    model.appendRow([legacy_qt.gui.QStandardItem('10')])
    qt = NS(QtCore=QtCore, QtGui=NS(QSortFilterProxyModel=QtCore.QSortFilterProxyModel, QHeaderView=QtWidgets.QHeaderView))
    table_sorting.install(panel, view, model, qt, numeric=(0,))
    assert panel._sort_proxy.lessThan(NS(data='2', column=0), NS(data='10', column=0))
    assert panel._sort_proxy.lessThan(NS(data='U+FFF0', column=0), NS(data='U+10000', column=0))
    assert panel._sort_proxy.lessThan(NS(data='A', column=0), NS(data='B', column=0))
    assert table_sorting.source_row(panel, table_sorting.editor_index(panel, view.model().index(0, 0), qt)) == 0
    raw = NS(row=3)
    assert table_sorting.editor_index(NS(), raw, qt) is raw
    with pytest.raises(ValueError, match="no longer present"):
        table_sorting.source_row(NS(), NS(row=-1))


def test_sorted_unicode_dock_activation_keeps_source_identity(profile_host, monkeypatch):
    from PySide6 import QtCore, QtWidgets
    from fontlabapp.core import scripting
    from fontlabapp.fontui.core_pythonqt_labs.profiles import unicode_issues_dock as module
    qt, owned = profile_host
    host = QtWidgets.QMainWindow()
    owned.append(host)
    monkeypatch.setattr(scripting, 'current_package', lambda *args: NS(id=1))
    selected = []
    monkeypatch.setattr(scripting, 'select_glyphs', lambda names, **kwargs: selected.extend(names) or names)
    panel = module.show(qt, host, capture=lambda: NS(rows=(('B', '', ''), ('A', '', ''))), embedded=True)
    panel.issue_view.sortByColumn(0, QtCore.Qt.AscendingOrder)
    panel.issue_view.doubleClicked.emit(panel.issue_view.model().index(0, 0))
    assert selected == ['A']
    assert panel.page_rows[0][0] == 'B'
    assert panel.close_owned()


def test_unicode_map_sorted_refresh_preserves_complete_rows_on_success_and_failure(profile_host, monkeypatch):
    from PySide6 import QtCore, QtWidgets
    from fontlabapp.core import scripting
    from fontlabapp.fontui.core_pythonqt_labs.profiles import apply_unicode_map as module
    monkeypatch.setattr(scripting, 'current_package', lambda *args: None)
    panel = module.build(None)
    profile_host[1].append(panel)
    base = type(panel).__mro__[1]
    def fill(owner, *args):
        assert not owner.table.isSortingEnabled()
        owner.table.setRowCount(2)
        for row, (name, code) in enumerate([('B', 'U+0042'), ('A', 'U+0041')]):
            owner.table.setItem(row, 0, QtWidgets.QTableWidgetItem(name))
            owner.table.setItem(row, 1, QtWidgets.QTableWidgetItem(code))
    monkeypatch.setattr(base, 'refresh', fill)
    panel.table.sortItems(0, QtCore.Qt.AscendingOrder)
    panel.refresh()
    assert panel.table.item(0, 0).text() == 'A'
    assert panel.table.item(0, 1).text() == 'U+0041'
    def fail(owner, *args):
        raise RuntimeError('capture failed')
    monkeypatch.setattr(base, 'refresh', fail)
    with pytest.raises(RuntimeError, match='capture failed'):
        panel.refresh()
    assert panel.table.isSortingEnabled()
