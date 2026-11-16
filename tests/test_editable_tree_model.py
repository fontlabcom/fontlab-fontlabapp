# this_file: tests/test_editable_tree_model.py
"""Real Qt editing and persistent-index controls for both original policies."""

import os

import pytest

from fontlabapp.qt.trees.editable.model import model_type
from fontlabapp.qt.trees.editable.view import ExpandedRows
from fontlabapp.qt.trees.data import Tree

if os.environ.get("FONTLABAPP_TEST_QT5") == "1":
    from PyQt5 import QtCore, QtGui, QtWidgets
    from PyQt5.QtTest import QAbstractItemModelTester
else:
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtTest import QAbstractItemModelTester

APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
APP.setFont(QtGui.QFont("Helvetica"))
QtGui.QFontMetrics(APP.font()).height()
SOURCE = Tree(
    ("Glyph", "Value"),
    (
        (-1, ("A", "")),
        (0, ("Unicode", "U+0041")),
        (1, ("Detail", "nested")),
        (-1, ("B", "")),
    ),
)


@pytest.fixture(params=[False, True])
def model(request):
    instance = model_type(QtCore)(SOURCE, official=request.param)
    yield instance, request.param
    instance.deactivate()
    instance.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_complete_read_and_edit_interfaces_keep_each_original_value_policy(model):
    m, official = model
    invalid = QtCore.QModelIndex()
    a, b = m.index(0, 0), m.index(1, 0)
    child = m.index(0, 0, a)
    assert m.rowCount() == 2 and m.columnCount() == 2
    assert m.parent(child) == a and not m.parent(a).isValid()
    assert not m.parent(invalid).isValid()
    assert m.data(child) == "Unicode" and m.data(child, QtCore.Qt.EditRole) == "Unicode"
    assert m.data(a, QtCore.Qt.ToolTipRole) is None
    assert m.data(invalid) is None
    assert (
        m.flags(a)
        == QtCore.Qt.ItemIsEditable
        | QtCore.Qt.ItemIsSelectable
        | QtCore.Qt.ItemIsEnabled
    )
    assert m.flags(invalid) == QtCore.Qt.NoItemFlags
    assert m.rowCount(m.index(0, 1)) == 0
    assert not m.index(0, 0, m.index(0, 1)).isValid()
    assert m.headerData(0, QtCore.Qt.Horizontal) == "Glyph"
    assert m.headerData(-1, QtCore.Qt.Horizontal) is None
    assert m.headerData(0, QtCore.Qt.Vertical) is None
    assert m.headerData(0, QtCore.Qt.Horizontal, QtCore.Qt.EditRole) is None
    changes, headers = [], []
    m.dataChanged.connect(lambda *args: changes.append(args))
    m.headerDataChanged.connect(lambda *args: headers.append(args))
    assert m.setData(b, 42)
    assert m.data(b) == (42 if official else "42")
    assert m.setData(child, None)
    assert m.data(child) == (None if official else "None")
    assert m.setHeaderData(0, QtCore.Qt.Horizontal, 7)
    assert m.headerData(0, QtCore.Qt.Horizontal) == (7 if official else "7")
    assert len(changes) == 2 and len(headers) == 1
    assert not m.setData(a, "wrong role", QtCore.Qt.DisplayRole)
    assert not m.setData(invalid, "root")
    assert not m.setHeaderData(0, QtCore.Qt.Vertical, "vertical")
    assert not m.setHeaderData(-1, QtCore.Qt.Horizontal, "bad")
    assert m.setHeaderData(
        0, QtCore.Qt.Horizontal, "display", QtCore.Qt.DisplayRole
    ) is (not official)
    assert SOURCE.rows[1][1][0] == "Unicode"


def test_row_notifications_preserve_sibling_and_descendant_persistent_indexes(model):
    m, official = model
    a = m.index(0, 0)
    b = QtCore.QPersistentModelIndex(m.index(1, 0))
    deep = QtCore.QPersistentModelIndex(m.index(0, 1, m.index(0, 0, a)))
    signals = []
    m.rowsAboutToBeInserted.connect(
        lambda *args: signals.append(("before", m.rowCount(), args))
    )
    m.rowsInserted.connect(lambda *args: signals.append(("after", m.rowCount(), args)))
    assert m.insertRows(1, 2)
    assert b.row() == 3 and b.data() == "B"
    assert deep.isValid() and deep.data() == "nested"
    assert [s[:2] for s in signals] == [("before", 2), ("after", 4)]
    assert m.data(m.index(1, 0)) == (None if official else "New entry")
    assert m.data(m.index(1, 1)) == (None if official else "")
    assert m.removeRows(1, 2)
    assert b.row() == 1 and deep.isValid()
    assert m.removeRows(0, 1)
    assert not deep.isValid() and b.isValid() and b.row() == 0
    assert m.rowCount() == 1


def test_global_column_layout_keeps_hierarchy_and_all_persistent_values(model):
    m, official = model
    a = m.index(0, 0)
    child = m.index(0, 0, a)
    saved = [
        QtCore.QPersistentModelIndex(i)
        for i in (a, child, m.index(0, 1, child), m.index(1, 1))
    ]
    values = [i.data() for i in saved]
    changes = []
    # Capture persistent handles created by a listener during the before signal.
    late = []

    def before(*args):
        changes.append(("before", m.columnCount()))
        late.append(QtCore.QPersistentModelIndex(m.index(1, 0)))

    m.layoutAboutToBeChanged.connect(before)
    m.layoutChanged.connect(lambda *args: changes.append(("after", m.columnCount())))
    assert m.insertColumns(0, 2, child)
    assert changes == [("before", 2), ("after", 4)]
    assert [i.data() for i in saved] == values
    assert [i.column() for i in saved] == [2, 2, 3, 3]
    assert late[0].column() == 2 and late[0].data() == "B"
    assert m.rowCount(m.index(0, 0)) == 1
    assert m.rowCount(m.index(0, 0, m.index(0, 0))) == 1
    assert saved[2].parent().column() == 0
    assert m.headerData(0, QtCore.Qt.Horizontal) == (None if official else "Column")
    assert m.data(m.index(0, 0)) == (None if official else "")
    assert m.removeColumns(0, 2)
    assert [i.data() for i in saved] == values and [i.column() for i in saved] == [
        0,
        0,
        1,
        1,
    ]
    doomed = QtCore.QPersistentModelIndex(m.index(0, 1))
    survivor = QtCore.QPersistentModelIndex(m.index(0, 0))
    assert m.removeColumns(1, 1)
    assert not doomed.isValid() and survivor.isValid() and survivor.data() == "A"


def test_last_column_policy_and_empty_tree_recovery(model):
    m, official = model
    saved = QtCore.QPersistentModelIndex(m.index(0, 0))
    assert m.removeColumns(0, 2)
    assert m.columnCount() == 0 and m.rowCount() == (0 if official else 2)
    assert not saved.isValid() and not m.index(0, 0).isValid()
    assert m.insertColumns(0, 1)
    assert m.columnCount() == 1 and m.rowCount() == (0 if official else 2)
    if not official:
        assert m.rowCount(m.index(0, 0)) == 1
        assert m.removeRows(0, 2)
    assert m.insertRows(0, 1)
    assert m.rowCount() == 1


@pytest.mark.parametrize(
    "method,args",
    [
        ("insertRows", (-1, 1)),
        ("insertRows", (3, 1)),
        ("insertRows", (0, 0)),
        ("insertRows", (0, 10**100)),
        ("removeRows", (1, 2)),
        ("removeRows", (0, -1)),
        ("insertColumns", (3, 1)),
        ("insertColumns", (0, 10**100)),
        ("removeColumns", (0, 3)),
        ("removeColumns", (-1, 1)),
        ("insertRows", (None, 1)),
        ("insertColumns", (0, True)),
    ],
)
def test_rejected_changes_emit_no_notifications_and_preserve_complete_data(
    model, method, args
):
    m, _ = model
    saved = QtCore.QPersistentModelIndex(m.index(1, 0))
    before = m._draft.fork()
    emitted = []
    for signal in (
        m.rowsAboutToBeInserted,
        m.rowsAboutToBeRemoved,
        m.layoutAboutToBeChanged,
    ):
        signal.connect(lambda *args: emitted.append(args))
    assert not getattr(m, method)(*args)
    assert not emitted and saved.isValid() and saved.data() == "B"
    assert m._draft.cells(0) == before.cells(0) and m._draft.children(
        0
    ) == before.children(0)
    assert m.error


def test_foreign_removed_and_mismatched_indexes_cannot_edit_or_select(model):
    m, _ = model
    foreign = model_type(QtCore)(SOURCE)
    try:
        for method in ("insertRows", "removeRows", "insertColumns", "removeColumns"):
            assert not getattr(m, method)(0, 1, foreign.index(0, 0))
        assert m.data(foreign.index(0, 0)) is None
        assert not m.setData(foreign.index(0, 0), "foreign")
        stale = m.index(0, 0, m.index(0, 0))
        assert m.removeRows(0, 1)
        assert m.data(stale) is None and not m.setData(stale, "stale")
        malformed = m.createIndex(99, 0, 4)
        assert m.flags(malformed) == QtCore.Qt.NoItemFlags
        assert not m.insertRows(0, 1, m.index(0, 1))
        assert not m.removeRows(0, 1, m.index(0, 1))
    finally:
        foreign.deactivate()
        foreign.deleteLater()


def test_real_qt_tester_and_view_keep_editing_over_successive_structural_changes(model):
    m, _ = model
    messages = []
    previous = QtCore.qInstallMessageHandler(
        lambda kind, context, message: messages.append(message)
    )
    view = QtWidgets.QTreeView()
    view.setModel(m)
    expansion = ExpandedRows(view, m)
    connections = [
        (view.expanded, expansion.expanded),
        (view.collapsed, expansion.collapsed),
        (m.rowsRemoved, expansion.prune),
        (m.layoutChanged, expansion.restore),
    ]
    for signal, slot in connections:
        signal.connect(slot)
    try:
        tester = QAbstractItemModelTester(
            m, QAbstractItemModelTester.FailureReportingMode.Warning
        )
        view.expandAll()
        assert expansion.identities == {1, 2, 3, 4}
        view.setCurrentIndex(m.index(0, 1))
        for iteration in range(3):
            assert m.insertRows(0, 1, m.index(0, 0))
            assert m.setData(m.index(0, 0, m.index(0, 0)), f"child{iteration}")
            assert m.insertColumns(0, 1)
            assert view.currentIndex().column() == 2
            assert view.header().count() == 3
            assert view.isExpanded(m.index(0, 0))
            assert m.removeColumns(0, 1)
            assert view.currentIndex().column() == 1
            assert m.removeRows(0, 1, m.index(0, 0))
        assert m.removeColumns(0, 2)
        assert m.insertColumns(0, 2)
        APP.processEvents()
        assert not messages, messages
        del tester
    finally:
        for signal, slot in reversed(connections):
            signal.disconnect(slot)
        expansion.dispose()
        view.setModel(None)
        view.deleteLater()
        QtCore.qInstallMessageHandler(previous)


def test_reentrant_edits_are_refused_and_deactivation_waits_for_notification_pair(
    model,
):
    m, _ = model
    nested, after = [], []

    def before(*args):
        nested.append(m.insertRows(0, 1))
        m.deactivate()

    m.layoutAboutToBeChanged.connect(before)
    m.layoutChanged.connect(lambda *args: after.append(m.columnCount()))
    assert m.insertColumns(0, 1)
    assert nested == [False] and after == [3]
    assert not m._active and m.rowCount() == 0 and m.columnCount() == 0
    assert not m.insertRows(0, 1) and not m.removeRows(0, 1)
    assert not m.insertColumns(0, 1) and not m.removeColumns(0, 1)
    assert not m.setData(None, "x")
    assert not m.setHeaderData(0, QtCore.Qt.Horizontal, "x")
    assert m.headerData(0, QtCore.Qt.Horizontal) is None
    assert m.data(None) is None and m.flags(None) == QtCore.Qt.NoItemFlags
    assert not m.index(0, 0).isValid() and not m.parent(None).isValid()


def test_invalid_construction_is_refused_before_native_model():
    with pytest.raises(TypeError):
        model_type(QtCore)(None)
    with pytest.raises(TimeoutError):
        model_type(QtCore)(SOURCE, deadline=0)


def test_pythonqt_gui_model_location_and_callable_signal_emission():
    from types import SimpleNamespace

    from fontlabapp.qt.trees.editable.base import emit

    core = SimpleNamespace(Qt=QtCore.Qt, QModelIndex=QtCore.QModelIndex)
    gui = SimpleNamespace(QAbstractItemModel=QtCore.QAbstractItemModel)
    m = model_type(core, gui)(SOURCE)
    try:
        assert m.rowCount() == 2 and m.insertColumns(0, 1)
        seen = []
        emit(lambda *args: seen.extend(args), 1, 2)
        assert seen == [1, 2]
    finally:
        m.deactivate()
        m.deleteLater()


def test_preflight_deadline_failure_has_no_signals_or_data_delta(model, monkeypatch):
    import fontlabapp.qt.trees.editable.model as module

    m, _ = model
    events = []
    m.rowsAboutToBeInserted.connect(lambda *args: events.append(args))
    m.layoutAboutToBeChanged.connect(lambda *args: events.append(args))
    monkeypatch.setattr(module, "monotonic", lambda: 0)
    assert not m.insertRows(0, 1) and not m.insertColumns(0, 1)
    assert m.rowCount() == 2 and m.columnCount() == 2
    assert "expired" in m.error and not events


def test_failed_text_conversion_does_not_change_data_or_escape_native_boundary(model):
    m, official = model

    class Failing:
        def __str__(self):
            raise ValueError("refuse conversion")

    value = Failing()
    index = m.index(0, 0)
    if official:
        assert m.setData(index, value) and m.data(index) is value
    else:
        assert not m.setData(index, value) and m.data(index) == "A"
        assert "refuse conversion" in m.error


def test_expansion_callbacks_fence_deleted_views_and_contain_foreign_index_failures(
    model,
):
    m, _ = model
    view = QtWidgets.QTreeView()
    view.setModel(m)
    state = ExpandedRows(view, m)
    invalid = QtCore.QModelIndex()
    state.expanded(invalid)
    assert not state.identities
    state.expanded(m.index(0, 0))
    state.collapsed(m.index(0, 0))
    assert not state.identities
    state.expanded(m.createIndex(0, 0, 999))
    assert "Unknown" in state.error
    state.collapsed(m.createIndex(0, 0, 999))
    assert "Unknown" in state.error
    assert not m.node_index(0).isValid()
    assert not m.node_index(1, -1).isValid()
    assert not m.node_index(999).isValid()
    state.model = None
    state.prune()
    assert state.error
    state.view = None
    state.restore()
    assert state.error and not state._restoring
    state.dispose()
    state.expanded(None)
    state.collapsed(None)
    state.prune()
    state.restore()
    state.dispose()
    assert state.view is state.model is None and not state.identities
    view.setModel(None)
    view.deleteLater()


def test_selected_descendant_and_partial_expansion_survive_column_zero_changes(model):
    m, _ = model
    view = QtWidgets.QTreeView()
    view.setModel(m)
    state = ExpandedRows(view, m)
    connections = [
        (view.expanded, state.expanded),
        (view.collapsed, state.collapsed),
        (m.rowsRemoved, state.prune),
        (m.layoutChanged, state.restore),
    ]
    for signal, slot in connections:
        signal.connect(slot)
    try:
        view.setExpanded(m.index(0, 0), True)
        selected = m.index(0, 1, m.index(0, 0))
        view.setCurrentIndex(selected)
        for _ in range(2):
            assert m.insertColumns(0, 1)
            assert view.currentIndex().data() == "U+0041"
            assert view.currentIndex().column() == 2
            assert view.isExpanded(m.index(0, 0))
            assert not view.isExpanded(m.index(0, 0, m.index(0, 0)))
            assert m.removeColumns(0, 1)
            assert view.currentIndex().data() == "U+0041"
        assert m.removeRows(0, 1)
        assert not state.identities and not state.error
    finally:
        for signal, slot in reversed(connections):
            signal.disconnect(slot)
        state.dispose()
        view.setModel(None)
        view.deleteLater()
