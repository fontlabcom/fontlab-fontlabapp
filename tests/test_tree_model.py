# this_file: tests/test_tree_model.py
"""Real standalone Qt tree contracts, foreign indices and late virtual safety."""

import os

import pytest
from fontlabapp.qt.trees.readonly import model_type
from fontlabapp.qt.trees.data import Tree

if os.environ.get("FONTLABAPP_TEST_QT5") == "1":
    from PyQt5 import QtCore, QtWidgets
else:
    from PySide6 import QtCore, QtWidgets
APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture(params=[False, True])
def model(request):
    data = Tree(
        ("Name", "Summary"),
        (
            (-1, ("A", "root")),
            (0, ("child",)),
            (1, ("deep", "two", "three")),
            (-1, ("A", "second")),
        ),
    )
    result = model_type(QtCore)(data, outline=request.param)
    yield result, request.param
    result.deactivate()
    result.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_hierarchy_headers_columns_parent_rows_and_distinct_occurrences(model):
    m, outline = model
    invalid = QtCore.QModelIndex()
    assert m.rowCount() == 2 and m.columnCount() == 2
    a = m.index(0, 0)
    child = m.index(0, 0, a)
    deep = m.index(0, 0, child)
    second = m.index(1, 0)
    assert m.data(a) == m.data(second) == "A" and a != second
    assert (
        m.parent(child) == a and m.parent(deep) == child and not m.parent(a).isValid()
    )
    assert not m.parent(invalid).isValid() and m.rowCount(deep) == 0
    assert m.data(child) == "child" and m.columnCount(child) == (2 if outline else 1)
    assert m.rowCount(m.index(0, 1)) == 0 and not m.index(0, 0, m.index(0, 1)).isValid()
    assert m.headerData(0, QtCore.Qt.Horizontal) == "Name"
    assert m.headerData(-1, QtCore.Qt.Horizontal) is None
    assert m.headerData(0, QtCore.Qt.Vertical) is None
    assert m.headerData(0, QtCore.Qt.Horizontal, QtCore.Qt.EditRole) is None
    assert m.data(invalid) is None and m.flags(invalid) == QtCore.Qt.NoItemFlags
    assert m.data(a, QtCore.Qt.EditRole) == ("A" if outline else None)
    assert m.data(a, QtCore.Qt.ToolTipRole) is None
    assert m.flags(a) == QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
    assert not m.setData(a, "edit", QtCore.Qt.EditRole)
    assert not m.insertRows(0, 1, invalid) and not m.removeRows(0, 1, invalid)
    assert not m.insertColumns(0, 1, invalid) and not m.removeColumns(0, 1, invalid)
    assert not m.setHeaderData(0, QtCore.Qt.Horizontal, "edit", QtCore.Qt.EditRole)
    assert not m.error


@pytest.mark.parametrize("row,column", [(-1, 0), (2, 0), (0, -1), (0, 2)])
def test_out_of_domain_requested_indices_are_invalid(model, row, column):
    m, _ = model
    assert not m.index(row, column).isValid() and not m.error


def test_short_child_cell_returns_no_data_in_fixed_part2_columns(model):
    m, _outline = model
    child = m.index(0, 1, m.index(0, 0))
    assert m.data(child) is None
    assert child.isValid() is True


def test_foreign_obsolete_or_malformed_occurrence_is_contained(model):
    m, _ = model
    other = model_type(QtCore)(Tree(("A",), ((-1, ("foreign",)),)))
    assert m.data(other.index(0, 0)) is None and "Foreign" in m.error
    stale = m.createIndex(0, 0, 9999)
    assert m.rowCount(stale) == 0 and "obsolete" in m.error
    wrong = m.createIndex(10, 0, 1)
    assert m.flags(wrong) == QtCore.Qt.NoItemFlags and "occurrence" in m.error
    other.deleteLater()


def test_empty_tree_and_late_methods_are_inert_even_after_native_deletion():
    m = model_type(QtCore)(Tree(("A",), ()))
    assert m.rowCount() == 0 and m.columnCount() == 1 and not m.index(0, 0).isValid()
    m.deactivate()
    m.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    assert m.rowCount() == m.columnCount() == 0 and m.data(None) is None
    assert m.headerData(0, QtCore.Qt.Horizontal) is None
    assert not m.index(0, 0).isValid() and not m.parent(None).isValid()
    assert m.flags(None) == QtCore.Qt.NoItemFlags


def test_invalid_tree_or_expired_construction_is_refused_before_native_owner():
    factory = model_type(QtCore)
    with pytest.raises(TypeError):
        factory(None)
    with pytest.raises(TimeoutError):
        factory(Tree(("A",), ()), deadline=0)


def test_model_passes_real_qt_model_tester_on_complete_ragged_hierarchy(model):
    if os.environ.get("FONTLABAPP_TEST_QT5") == "1":
        from PyQt5.QtTest import QAbstractItemModelTester
    else:
        from PySide6.QtTest import QAbstractItemModelTester
    messages = []
    previous = QtCore.qInstallMessageHandler(
        lambda kind, context, message: messages.append(message)
    )
    try:
        tester = QAbstractItemModelTester(
            model[0], QAbstractItemModelTester.FailureReportingMode.Warning
        )
        APP.processEvents()
        assert not messages, messages
        del tester
    finally:
        QtCore.qInstallMessageHandler(previous)
