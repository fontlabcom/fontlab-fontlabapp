# this_file: src/fontlabapp/fontui/core_pythonqt_labs/profiles/table_sorting.py
# SPDX-License-Identifier: Apache-2.0
"""Lab table proxies keep the original captured model in source order."""
from typing import Any

from fontlabapp.qt.properties import value


def install(panel: Any, view: Any, model: Any, qt: Any, *, numeric: tuple[int, ...] = ()) -> None:
    """Sort the visible rows without reordering the model used by writers."""
    core = qt.QtCore
    proxy = getattr(panel, '_sort_proxy', None)
    if proxy is None:
        proxy_type = getattr(qt.QtGui, "QSortFilterProxyModel", None) or core.QSortFilterProxyModel

        class Proxy(proxy_type):
            def lessThan(self, left: Any, right: Any) -> bool:
                a, b = value(left, "data"), value(right, "data")
                if value(left, "column") in numeric:
                    try:
                        left_number = int(a[2:], 16) if str(a).startswith("U+") else float(a)
                        right_number = int(b[2:], 16) if str(b).startswith("U+") else float(b)
                        return left_number < right_number
                    except (TypeError, ValueError):
                        pass
                return str(a) < str(b)

        proxy = panel._sort_proxy = Proxy(view)
        proxy.setDynamicSortFilter(True)
        view.setModel(proxy)
        value(view, "horizontalHeader").setSectionResizeMode(qt.QtGui.QHeaderView.Interactive)
        view.setSortingEnabled(True)
        view.sortByColumn(-1, core.Qt.AscendingOrder)
    proxy.setSourceModel(model)


def source_row(panel: Any, index: Any) -> int:
    """Resolve presented and persistent editor indexes to captured source rows."""
    proxy = getattr(panel, '_sort_proxy', None)
    if proxy is not None:
        from PythonQt import QtCore
        index = proxy.mapToSource(QtCore.QModelIndex(index))
    row = int(value(index, 'row'))
    if row < 0:
        raise ValueError('The selected row is no longer present; refresh the table.')
    return row


def editor_index(panel: Any, index: Any, qt: Any) -> Any:
    """A live editor keeps its glyph when the user resorts before committing."""
    return qt.QtCore.QPersistentModelIndex(index) if getattr(panel, '_sort_proxy', None) is not None else index
