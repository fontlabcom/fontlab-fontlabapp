# this_file: src/fontlabapp/qt/trees/editable/editor.py
# SPDX-License-Identifier: Apache-2.0
"""Own one staged tree view, model, selection and exact signal scope."""

from typing import Any

from fontlabapp.qt.trees.editable.model import model_type
from fontlabapp.qt.trees.editable.view import ExpandedRows
from fontlabapp.core.signals.scope import Scope


class Editor:
    """Register with the panel before setup so failed cleanup retains ownership."""

    def __init__(self, qt: Any, panel: Any, snapshot: Any, deadline: float) -> None:
        self.view = self.model = self.selection = self.expansion = None
        self.released = False
        self.scope = Scope(panel._failure)
        panel._editors.append(self)
        self.view = qt.QtGui.QTreeView(panel)
        self.view.hide()
        self.model = model_type(qt.QtCore)(
            snapshot,
            self.view,
            official=panel.official,
            deadline=deadline,
        )
        self.view.setModel(self.model)
        self.selection = self.view.selectionModel()
        if panel.official:
            self.view.setAlternatingRowColors(True)
            self.view.setSelectionBehavior(qt.QtGui.QAbstractItemView.SelectItems)
            self.view.setHorizontalScrollMode(qt.QtGui.QAbstractItemView.ScrollPerPixel)
            self.view.setAnimated(False)
            self.view.setAllColumnsShowFocus(True)
        self.expansion = ExpandedRows(self.view, self.model)
        for signal, call in (
            (self.view.expanded, self.expansion.expanded),
            (self.view.collapsed, self.expansion.collapsed),
            (self.model.rowsRemoved, self.expansion.prune),
            (self.model.layoutChanged, self.expansion.restore),
            (self.selection.currentChanged, lambda *args: panel._selected(self)),
            (self.selection.selectionChanged, lambda *args: panel._selected(self)),
            (self.model.dataChanged, lambda *args: panel._changed(self)),
            (self.model.headerDataChanged, lambda *args: panel._changed(self)),
        ):
            self.scope.connect(signal, call)
        for column in range(self.model.columnCount()):
            self.view.resizeColumnToContents(column)

    def close(self, *, destroyed: bool = False) -> bool:
        """Disconnect before detaching/deleting; keep every failed owner for retry."""
        if self.released:
            return True
        if not destroyed and self.view is not None:
            self.view.setEnabled(False)
        if not self.scope.finish(destroyed=destroyed):
            return False
        if self.expansion is not None:
            self.expansion.dispose()
        if not destroyed:
            if self.view is not None:
                self.view.setModel(None)
            if self.selection is not None:
                self.selection.deleteLater()
                self.selection = None
        if self.model is not None:
            self.model.deactivate()
            if not destroyed:
                self.model.deleteLater()
        if self.view is not None and not destroyed:
            self.view.deleteLater()
        self.view = self.model = self.selection = self.expansion = None
        self.released = True
        return True
