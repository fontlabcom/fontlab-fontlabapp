# this_file: src/fontlabapp/qt/trees/editable/model.py
# SPDX-License-Identifier: Apache-2.0
"""Complete editable-tree Qt mutations with preflight and persistent remapping."""

from time import monotonic
from typing import Any

from fontlabapp.qt.trees.editable.base import base_type, emit, virtual
from fontlabapp.qt.trees.data import check_deadline


def model_type(core: Any, gui: Any = None) -> type:
    """Build both original policies using injected Qt and an owned local draft."""
    qt, invalid = core.Qt, core.QModelIndex

    class EditableModel(base_type(core, gui)):
        @virtual(lambda: False, write=True)
        def setData(self, index: Any, value: object, role: Any = qt.EditRole) -> bool:
            identity = self._identity(index)
            if not identity or role != qt.EditRole:
                return False
            self._draft.set_value(
                identity, index.column(), value if self.official else str(value)
            )
            self.edited = True
            emit(self.dataChanged, index, index, [])
            return True

        @virtual(lambda: False, write=True)
        def setHeaderData(
            self,
            section: int,
            orientation: Any,
            value: object,
            role: Any = qt.EditRole,
        ) -> bool:
            if orientation != qt.Horizontal or (self.official and role != qt.EditRole):
                return False
            self._draft.set_value(0, section, value if self.official else str(value))
            self.edited = True
            emit(self.headerDataChanged, orientation, section, section)
            return True

        def _row_change(self, row: int, count: int, parent: Any, insert: bool) -> bool:
            identity = self._identity(parent)
            if parent is not None and parent.isValid() and parent.column() != 0:
                raise ValueError("Only column zero can own tree children.")
            deadline = monotonic() + 2.0
            staged = self._draft.fork()
            if insert:
                width = staged.column_count
                cells = tuple("New entry" if c == 0 else "" for c in range(width))
                created = staged.insert_rows(identity, row, count, cells)
                if self.official:
                    for node in created:
                        for column in range(width):
                            staged.set_value(node, column, None)
            else:
                staged.remove_rows(identity, row, count)
            check_deadline(deadline)
            parent = invalid() if parent is None else parent
            before = self.beginInsertRows if insert else self.beginRemoveRows
            after = self.endInsertRows if insert else self.endRemoveRows
            before(parent, row, row + count - 1)
            self._draft, self.edited = staged, True
            after()
            return True

        @virtual(lambda: False, write=True)
        def insertRows(self, row: int, count: int, parent: Any = None) -> bool:
            return self._row_change(row, count, parent, True)

        @virtual(lambda: False, write=True)
        def removeRows(self, row: int, count: int, parent: Any = None) -> bool:
            return self._row_change(row, count, parent, False)

        def _column_change(
            self, column: int, count: int, parent: Any, insert: bool
        ) -> bool:
            self._identity(parent)
            deadline = monotonic() + 2.0
            staged = self._draft.fork()
            if insert:
                staged.insert_columns(column, count)
                if self.official:
                    for node in staged.identities():
                        for current in range(column, column + count):
                            staged.set_value(node, current, None)
            else:
                staged.remove_columns(column, count)
                if self.official and staged.column_count == 0 and staged.children(0):
                    staged.remove_rows(0, 0, len(staged.children(0)))
            check_deadline(deadline)
            # Global column edits reorganize every depth, rather than one parent.
            # Qt5's model/view reference permits layout signals plus remapping.
            emit(self.layoutAboutToBeChanged)
            previous = list(self.persistentIndexList())
            following = []
            live = set(staged.identities())
            for index in previous:
                old, identity = index.column(), int(index.internalId())
                current = old + count if insert and old >= column else old
                if not insert:
                    current = (
                        -1
                        if column <= old < column + count
                        else old - (count if old >= column else 0)
                    )
                following.append(
                    self.createIndex(staged.position(identity), current, identity)
                    if identity in live and current >= 0
                    else invalid()
                )
            self._draft, self.edited = staged, True
            self.changePersistentIndexList(previous, following)
            emit(self.layoutChanged)
            return True

        @virtual(lambda: False, write=True)
        def insertColumns(self, column: int, count: int, parent: Any = None) -> bool:
            return self._column_change(column, count, parent, True)

        @virtual(lambda: False, write=True)
        def removeColumns(self, column: int, count: int, parent: Any = None) -> bool:
            return self._column_change(column, count, parent, False)

    return EditableModel
