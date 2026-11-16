# this_file: src/fontlabapp/qt/trees/readonly.py
# SPDX-License-Identifier: Apache-2.0
"""Injected read-only QAbstractItemModel over immutable text-tree occurrences."""

from collections.abc import Callable
from functools import wraps
from time import monotonic
from typing import Any

from fontlabapp.qt.trees.data import Tree, check_deadline


def model_type(core: Any) -> type:
    """Build only against supplied Qt; do not import a binding or create an app."""
    qt, invalid = core.Qt, core.QModelIndex

    def virtual(fallback: Callable[[], Any]) -> Callable:
        def decorate(method: Callable) -> Callable:
            @wraps(method)
            def guarded(self: Any, *args: Any) -> Any:
                if not getattr(self, "_active", False):
                    return fallback()
                try:
                    return method(self, *args)
                except Exception as error:  # noqa: BLE001 - contain native UI/virtual teardown failures
                    self.error = str(error)
                    return fallback()

            return guarded

        return decorate

    class TreeModel(core.QAbstractItemModel):
        def __init__(
            self,
            snapshot: Tree,
            parent: Any = None,
            *,
            outline: bool = False,
            deadline: float | None = None,
        ) -> None:
            if not isinstance(snapshot, Tree):
                raise TypeError("Model needs a complete immutable Tree.")
            cells = (snapshot.headers,) + tuple(cells for _, cells in snapshot.rows)
            parents, positions = [0], [0]
            children = [[] for _ in cells]
            limit = monotonic() + 2.0 if deadline is None else deadline
            for identity, (parent_id, _) in enumerate(snapshot.rows, 1):
                check_deadline(limit)
                parent_id += 1
                positions.append(len(children[parent_id]))
                children[parent_id].append(identity)
                parents.append(parent_id)
            check_deadline(limit)
            core.QAbstractItemModel.__init__(self, parent)
            self._outline, self._snapshot, self.error = outline, snapshot, ""
            self._cells, self._parents = cells, parents
            self._positions, self._children = positions, children
            self._active = True

        def deactivate(self) -> None:
            """Call after detaching views; late virtual calls become inert."""
            self._active, self._snapshot = False, None
            self._cells, self._parents, self._positions, self._children = (), (), (), ()

        def _columns(self, identity: int) -> int:
            return len(self._cells[0 if self._outline else identity])

        def _identity(self, index: Any) -> int:
            if index is None or not index.isValid():
                return 0
            identity = int(index.internalId())
            if index.model() != self or not 0 < identity < len(self._cells):
                raise ValueError("Foreign or obsolete tree index.")
            if index.row() != self._positions[
                identity
            ] or not 0 <= index.column() < self._columns(self._parents[identity]):
                raise ValueError("Tree index is outside its occurrence.")
            return identity

        @virtual(lambda: 0)
        def columnCount(self, parent: Any = None) -> int:
            return self._columns(self._identity(parent))

        @virtual(lambda: 0)
        def rowCount(self, parent: Any = None) -> int:
            identity = self._identity(parent)
            if parent is not None and parent.isValid() and parent.column() != 0:
                return 0
            return len(self._children[identity])

        @virtual(invalid)
        def index(self, row: int, column: int, parent: Any = None) -> Any:
            identity = self._identity(parent)
            if parent is not None and parent.isValid() and parent.column() != 0:
                return invalid()
            if not 0 <= row < len(
                self._children[identity]
            ) or not 0 <= column < self._columns(identity):
                return invalid()
            return self.createIndex(row, column, self._children[identity][row])

        @virtual(invalid)
        def parent(self, index: Any) -> Any:
            identity = self._identity(index)
            parent_id = self._parents[identity]
            return (
                self.createIndex(self._positions[parent_id], 0, parent_id)
                if parent_id
                else invalid()
            )

        @virtual(lambda: None)
        def data(self, index: Any, role: Any = qt.DisplayRole) -> str | None:
            roles = (
                (qt.DisplayRole, qt.EditRole) if self._outline else (qt.DisplayRole,)
            )
            if role not in roles:
                return None
            identity = self._identity(index)
            if not identity:
                return None
            cells = self._cells[identity]
            return cells[index.column()] if index.column() < len(cells) else None

        @virtual(lambda: None)
        def headerData(
            self, section: int, orientation: Any, role: Any = qt.DisplayRole
        ) -> str | None:
            if (
                orientation == qt.Horizontal
                and role == qt.DisplayRole
                and 0 <= section < len(self._cells[0])
            ):
                return self._cells[0][section]
            return None

        @virtual(lambda: qt.NoItemFlags)
        def flags(self, index: Any) -> Any:
            return (
                qt.ItemIsEnabled | qt.ItemIsSelectable
                if self._identity(index)
                else qt.NoItemFlags
            )

    return TreeModel
