# this_file: tests/test_studio_feature_table.py
"""Stable identities and numeric sorting for preserved feature task tables."""
import importlib
import sys
from types import SimpleNamespace

from _studio_qt import studio_qt  # noqa: F401


def test_sorted_numeric_rows_keep_selected_source_identity(studio_qt, monkeypatch):  # noqa: F811
    monkeypatch.setitem(sys.modules, 'fontlabapp.features.editor.ui', SimpleNamespace(FeaturesDialog=object))
    monkeypatch.delitem(sys.modules, 'fontlabapp.features.identity_tools.table', raising=False)
    module = importlib.import_module('fontlabapp.features.identity_tools.table')
    table = studio_qt.modules.table.QtGui.QTableWidget(0, 2)
    dialog = SimpleNamespace(table=table, rows=[])
    module.fill(dialog, [('a', 100), ('b', 2), ('c', 30)])
    table.sortItems(1, studio_qt.QtCore.Qt.AscendingOrder)
    assert [table.item(row, 0).text() for row in range(3)] == ['b', 'c', 'a']
    table.selectRow(1)
    assert module.selected_row(dialog) == 2
    module.fill(dialog, [('a', 100), ('c', 30), ('b', 2)])
    assert module.selected_row(dialog) == 1
    table.setCurrentCell(-1, -1)
    assert module.selected_row(dialog) == -1
    module.fill(dialog, [])
    assert table.rowCount() == 0
    table.close()
    monkeypatch.delitem(sys.modules, 'fontlabapp.features.identity_tools.table', raising=False)
