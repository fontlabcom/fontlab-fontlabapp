# this_file: src/fontlabapp/fontui/core_pythonqt_labs/profiles/lesson_lists.py
# SPDX-License-Identifier: Apache-2.0
"""Add lab-only sorting to retained Lessons lists without changing source models."""
from typing import Any

from fontlabapp.qt.properties import value


def name_order(child: Any, qt: Any) -> None:
    """Sort visible names and restore selection by exact name, never old row number."""
    child.lab_sort = qt.QtGui.QComboBox(child)
    child.lab_sort.addItems(['Font order', 'Name ascending', 'Name descending'])
    child.lab_sort.setAccessibleName('Glyph name order')
    child.content.insertWidget(0, child.lab_sort)
    original = child.apply_filter
    selection_kind = getattr(qt.QtGui, 'QItemSelectionModel', None) or qt.QtCore.QItemSelectionModel

    def apply_filter() -> None:
        selected = {child.visible_names[index.row()] for index in child.view.selectedIndexes()}
        original()
        mode = int(value(child.lab_sort, 'currentIndex'))
        if mode:
            child.model.sort(0, qt.QtCore.Qt.AscendingOrder if mode == 1 else qt.QtCore.Qt.DescendingOrder)
            child.visible_names = tuple(child.model.stringList())
        selection = child.view.selectionModel()
        for row, name in enumerate(child.visible_names):
            if name in selected:
                selection.select(child.model.index(row, 0), selection_kind.Select)

    child.apply_filter = apply_filter
    child._connect(child.lab_sort.currentIndexChanged, lambda *args: child.apply_filter())


def metric_order(child: Any, qt: Any) -> None:
    """Use Qt's numeric QVariant sorting, retaining source metrics and selection."""
    kind = getattr(qt.QtGui, 'QSortFilterProxyModel', None) or qt.QtCore.QSortFilterProxyModel
    child.lab_proxy = kind(child)
    child.lab_proxy.setDynamicSortFilter(True)
    original = child.set_model

    def set_model(model: Any) -> None:
        original(model)
        child.lab_proxy.setSourceModel(model)
        child.view.setModel(child.lab_proxy)

    child.set_model = set_model
    child.lab_proxy.setSourceModel(child.model)
    child.view.setModel(child.lab_proxy)
    header = value(child.view, 'horizontalHeader')
    header.setSectionResizeMode(qt.QtGui.QHeaderView.Interactive)
    header.setStretchLastSection(False)
    header.setSortIndicator(-1, qt.QtCore.Qt.AscendingOrder)
    child.view.setSortingEnabled(True)


def configure(child: Any, name: str) -> Any:
    """Keep the packaged form unchanged; upgrade only the two flat lab lists."""
    from fontlabapp import _native
    qt = _native('PythonQt')
    if name == 'glyph-name-filter':
        name_order(child, qt)
    elif name == 'glyph-metrics-model':
        metric_order(child, qt)
    return child
