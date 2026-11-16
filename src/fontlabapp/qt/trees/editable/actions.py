# this_file: src/fontlabapp/qt/trees/editable/actions.py
# SPDX-License-Identifier: Apache-2.0
"""Keep both original row/column/child and selection policies explicit."""

from typing import Any

from fontlabapp.qt.properties import value


class Controller:
    def __init__(self, panel: Any, qt: Any) -> None:
        self.panel, self.qt = panel, qt

    def _require(self, changed: bool) -> None:
        if not changed:
            raise ValueError(
                self.panel.editor.model.error or "The local tree refused the edit."
            )

    def run(self, operation: str) -> None:
        p = self.panel
        if p._closed or p.editor is None:
            return
        e, official = p.editor, p.official
        m, current = e.model, e.view.currentIndex()
        parent = m.parent(current)
        if operation == "child":
            owner = (
                m.index(current.row(), 0, parent)
                if current.isValid()
                else self.qt.QtCore.QModelIndex()
            )
            if official and m.columnCount() == 0:
                self._require(m.insertColumns(0, 1))
            row = 0 if official else m.rowCount(owner)
            self._require(m.insertRows(row, 1, owner))
            if official:
                self._fill(row, owner, headers=True)
                e.selection.setCurrentIndex(
                    m.index(row, 0, owner),
                    self.qt.QtGui.QItemSelectionModel.ClearAndSelect,
                )
        elif operation == "sibling":
            row = current.row() + int(official) if current.isValid() else m.rowCount()
            self._require(m.insertRows(row, 1, parent))
            if official:
                self._fill(row, parent)
        elif operation == "remove":
            if current.isValid():
                self._require(m.removeRows(current.row(), 1, parent))
        elif operation == "column":
            column = current.column() + 1 if official else m.columnCount()
            self._require(m.insertColumns(column, 1))
            if official:
                self._require(
                    m.setHeaderData(column, self.qt.QtCore.Qt.Horizontal, "[No header]")
                )
        elif operation == "remove_column":
            if (official and current.isValid()) or (
                not official and m.columnCount() > 1
            ):
                self._require(
                    m.removeColumns(
                        current.column() if official else m.columnCount() - 1, 1
                    )
                )
        else:
            raise ValueError("Unknown tree operation.")
        self.update()
        p._changed(e)

    def _fill(self, row: int, parent: Any, *, headers: bool = False) -> None:
        m, qt = self.panel.editor.model, self.qt.QtCore.Qt
        for column in range(m.columnCount()):
            self._require(
                m.setData(m.index(row, column, parent), "[No data]", qt.EditRole)
            )
            if headers and m.headerData(column, qt.Horizontal) is None:
                self._require(m.setHeaderData(column, qt.Horizontal, "[No header]"))

    def update(self, *, initial: bool = False) -> None:
        p = self.panel
        if p._closed:
            return
        e = p.editor
        current = (
            e.view.currentIndex() if e is not None else self.qt.QtCore.QModelIndex()
        )
        if p.official:
            # PythonQt exposes the selection Q_PROPERTY as a value; PySide6 as a method.
            selected = e is not None and not value(e.selection, "selection").isEmpty()
            for label in ("Remove Row", "Remove Column"):
                p.menu_actions[label].setEnabled(selected)
            for label in ("Insert Row", "Insert Column"):
                p.menu_actions[label].setEnabled(current.isValid())
            p.menu_actions["Insert Child"].setEnabled(e is not None)
            if current.isValid():
                e.view.closePersistentEditor(current)
                suffix = " in top level" if not current.parent().isValid() else ""
                p.selection_status.setText(
                    f"Position: ({current.row()},{current.column()}){suffix}"
                )
            else:
                p.selection_status.setText("" if initial else "No selection")
        else:
            for label, action in p.menu_actions.items():
                if label != "Exit":
                    action.setEnabled(e is not None)
            p.selection_status.setText(
                f"Row {current.row() + 1}, column {current.column() + 1}"
                if current.isValid()
                else "Select an entry"
                if initial
                else "No selection"
            )
