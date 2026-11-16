# this_file: tests/test_core_pythonqt_profiles_widgets.py
"""Construct the lab routes using the existing real Qt compatibility fixtures."""
import importlib
from types import SimpleNamespace

import pytest
from fontlabapp.fontui.core_pythonqt_labs.profiles import e01_e03 as routes
from fontlabapp.fontui.core_pythonqt_labs.profiles.e01_e03_actions import names
from test_editable_glyph_tree_dialog import panel as edit_panel  # noqa: F401
from test_filter_table_dialog import panel as filter_panel  # noqa: F401
from test_glyph_tree_dialog import panel as tree_panel  # noqa: F401
from test_spacing_worksheet import GUI, QtCore, drain


def test_filter_routes_construct_real_models_and_keep_identity(filter_panel, monkeypatch):  # noqa: F811
    existing, state, *_unused = filter_panel
    from fontlabapp.glyphs.catalog import native
    monkeypatch.setattr(native, 'capture', existing._capture)
    for title, build in routes.PROFILES['E01'][1:5]:
        child = build(None)
        try:
            assert child.model.rowCount() == len(state.rows)
            child.proxy.sort(0, QtCore.Qt.DescendingOrder)
            index = child.proxy.index(0, 0)
            source = child.proxy.mapToSource(index)
            assert child.proxy.data(index) == child.model.data(source)
            assert child.proxy_view.model() is child.proxy
            assert names(child, title)[0] == str(child.proxy.data(index))
        finally:
            assert child.close()
    drain()


def test_readonly_tree_routes_construct_original_models(tree_panel, monkeypatch):  # noqa: F811
    existing, _state, _outline = tree_panel
    import fontlabapp.glyphs.tree.model as source
    monkeypatch.setattr(source, 'capture', existing._capture)
    for title, build in routes.PROFILES['E02'][:2]:
        child = build(None)
        try:
            assert child.model.rowCount() == 2
            assert names(child, title) == ()
            child.view.setCurrentIndex(child.model.index(0, 0, child.model.index(0, 0)))
            assert names(child, title) == ('A',)
            assert not (child.model.flags(child.model.index(0, 0)) & QtCore.Qt.ItemIsEditable)
        finally:
            assert child.close()
    drain()


def test_editable_tree_routes_keep_distinct_drafts(edit_panel, monkeypatch):  # noqa: F811
    existing, state, _module = edit_panel
    import fontlabapp.glyphs.tree.model as source
    monkeypatch.setattr(source, 'capture', existing._capture)
    for title, build in routes.PROFILES['E02'][2:]:
        child = build(None)
        try:
            model = child.editor.model
            assert model.rowCount() == 2
            assert model.setData(model.index(0, 0), 'local draft', QtCore.Qt.EditRole)
            assert model.data(model.index(0, 0)) == 'local draft'
            child.editor.view.setCurrentIndex(model.index(0, 0))
            assert names(child, title) == ('A',)
            child.refresh()
            assert names(child, title) == ('A',)
            child.refresh(discard=True)
            model = child.editor.model
            child.editor.view.setCurrentIndex(model.index(0, 0))
            assert names(child, title) == ('A',)
            assert model.insertRows(0, 1)
            child.editor.view.setCurrentIndex(model.index(0, 0))
            assert names(child, title) == ()
            child.editor.view.setCurrentIndex(model.index(1, 0))
            assert names(child, title) == ('A',)
            assert state.source.rows[0][1][0] == 'A'
        finally:
            assert child.close()
    drain()


@pytest.mark.parametrize('index', [2, 3, 4, 5, 7, 8])
def test_metric_routes_construct_all_native_controls(monkeypatch, index):
    import fontlabapp
    from fontlabapp.metrics.offset.model import Snapshot as Offset
    from fontlabapp.metrics.worksheet.data import Baseline
    from fontlabapp.metrics.worksheet.data import Snapshot as Worksheet
    from fontlabapp.proof.numeric.model import Facts
    monkeypatch.setattr(fontlabapp, '_native', lambda name: SimpleNamespace(QtCore=QtCore, QtGui=GUI))
    for module, facts in [('proof.numeric.launcher', Facts(1000, (), ())),
                          ('metrics.offset.capture', Offset((1, 'R'), ())),
                          ('metrics.worksheet.capture', Worksheet((1, 'R'), (Baseline(1, 2, 3, 'A', 'R', 500),)) )]:
        monkeypatch.setattr(importlib.import_module('fontlabapp.' + module), 'capture', lambda facts=facts: facts)
    _title, build = routes.PROFILES['E03'][index]
    child = build(None)
    try:
        assert child.layout() is not None
        assert not child.last_error
        child.refresh()
        assert not child.last_error
    finally:
        assert child.close()
    drain()


def test_pattern_route_constructs_actual_editable_controls(monkeypatch):
    import fontlabapp
    import fontlabapp.glyphs.pattern as source
    from test_regexp_panel import core_for_panel
    monkeypatch.setattr(fontlabapp, '_native', lambda name: SimpleNamespace(QtCore=core_for_panel(), QtGui=GUI))
    monkeypatch.setattr(source, '_capture', lambda **kwargs: ('A', 'B'))
    child = routes.PROFILES['E01'][6][1](None)
    try:
        assert child.pattern.isEditable() and child.input.isEditable()
        assert child.words == ('A', 'B')
        child.pattern.setEditText('A.*')
        assert child.configuration()[0].pattern == 'A.*'
        assert names(child, 'Glyph Name Pattern Lab') == ('A', 'B')
    finally:
        assert child.close()
    drain()


class _LessonSource:
    """App-owned stand-in for the packaged Lessons data: font identity, names, selection, metrics."""

    def __init__(self):
        self.package = SimpleNamespace(id=14, master='Regular')
        self.names = ['space', 'A', 'Aacute', 'zero']
        self.selected = ['zero', 'A']
        self.rows = {'A': (2, 0), 'zero': (10, 0)}
        self.calls = []


def _fake_lessons(source):
    """A minimal fontlab_python_lessons.ui.dialog_type with the surface the lab routes rely on.

    The packaged dialogs are tested in the Examples repository; this fixture covers the App side
    (lesson_lists.configure and the route builders) without needing that sibling checkout.
    """
    from PySide6 import QtGui as Gui
    from PySide6 import QtWidgets as W

    class Base(W.QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.content = W.QVBoxLayout(self)
            self.snapshot = None
            self.visible_names = ()

        def _connect(self, signal, slot):
            signal.connect(slot)

        def snapshot_rows(self):
            return [SimpleNamespace(name=n, advance=source.rows[n][0]) for n in source.names if n in source.selected]

        def refresh(self):
            self.snapshot = SimpleNamespace(package_id=source.package.id, rows=self.snapshot_rows())
            self.show_snapshot()

    class NameFilter(Base):
        def __init__(self, parent=None):
            super().__init__(parent)
            from PySide6.QtCore import QStringListModel
            self.model = QStringListModel(self)
            self.view = W.QListView(self)
            self.view.setModel(self.model)
            self.content.addWidget(self.view)
            self.refresh()

        def snapshot_rows(self):
            return [SimpleNamespace(name=n) for n in source.names]

        def show_snapshot(self):
            self.apply_filter()

        def apply_filter(self):
            self.model.setStringList(list(source.names))
            self.visible_names = tuple(source.names)

        def select(self):
            source.calls.append(([self.visible_names[i.row()] for i in self.view.selectedIndexes()],))

    class MetricsModel(Base):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.view = W.QTableView(self)
            self.content.addWidget(self.view)
            self.set_model(Gui.QStandardItemModel(self))
            self.refresh()

        def set_model(self, model):
            self.model = model
            self.view.setModel(model)

        def show_snapshot(self):
            model = Gui.QStandardItemModel(self)
            for row in self.snapshot.rows:
                name = Gui.QStandardItem(row.name)
                advance = Gui.QStandardItem()
                advance.setData(row.advance, QtCore.Qt.EditRole)
                model.appendRow([name, advance])
            self.set_model(model)

    class MetricsForm(Base):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.refresh()

        def show_snapshot(self):
            pass

    def dialog_type(name):
        return {'glyph-name-filter': NameFilter, 'glyph-metrics-model': MetricsModel,
                'glyph-metrics-form': MetricsForm}[name]

    return SimpleNamespace(dialog_type=dialog_type)


@pytest.mark.parametrize('lab,index', [('E01', 0), ('E03', 0), ('E03', 1)])
def test_lesson_routes_construct_controls_against_app_owned_lessons_fake(monkeypatch, lab, index):
    import sys
    import fontlabapp
    source = _LessonSource()
    package = SimpleNamespace(__path__=[])
    monkeypatch.setitem(sys.modules, 'fontlab_python_lessons', package)
    monkeypatch.setitem(sys.modules, 'fontlab_python_lessons.ui', _fake_lessons(source))
    monkeypatch.setattr(fontlabapp, '_native', lambda name: SimpleNamespace(QtCore=QtCore, QtGui=GUI))
    host = SimpleNamespace(source=source)
    title, build = routes.PROFILES[lab][index]
    child = build(None)
    try:
        assert child.snapshot is not None
        assert child.snapshot.package_id == host.source.package.id
        child.refresh()
        assert child.snapshot is not None
        if title == 'Glyph Name Filter':
            assert names(child, title) == tuple(host.source.names)
            child.view.selectionModel().select(child.model.index(0, 0), QtCore.QItemSelectionModel.Select)
            selected_name = child.visible_names[0]
            child.lab_sort.setCurrentIndex(2)
            assert tuple(child.model.stringList()) == tuple(sorted(host.source.names, reverse=True))
            assert child.visible_names == tuple(child.model.stringList())
            child.select()
            assert host.source.calls[-1][0] == [selected_name]
            child.lab_sort.setCurrentIndex(1)
            assert tuple(child.model.stringList()) == tuple(sorted(host.source.names))
            child.lab_sort.setCurrentIndex(0)
            assert names(child, title) == tuple(host.source.names)
        elif title == 'Glyph Metrics Model':
            assert child.view.isSortingEnabled()
            proxy = child.view.model()
            child.view.selectionModel().select(proxy.index(0, 0), QtCore.QItemSelectionModel.Select)
            child.view.sortByColumn(1, QtCore.Qt.DescendingOrder)
            assert names(child, title) == ('zero', 'A')
            assert [str(proxy.data(i)) for i in child.view.selectedIndexes()] == ['A']
            child.view.horizontalHeader().resizeSection(0, 260)
            assert child.view.horizontalHeader().sectionSize(0) == 260
            child.refresh()
            proxy = child.view.model()
            assert names(child, title) == ('zero', 'A')
            assert proxy.sourceModel() is child.model
            for row in range(proxy.rowCount()):
                index = proxy.index(row, 0)
                assert proxy.data(index) == child.model.data(proxy.mapToSource(index))
            assert names(child, title) == tuple(str(proxy.data(proxy.index(row, 0))) for row in range(proxy.rowCount()))
        else:
            assert names(child, title) == tuple(row.name for row in child.snapshot.rows)
    finally:
        child.close()
        drain()
