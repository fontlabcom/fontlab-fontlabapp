# this_file: src/fontlabapp/qt/trees/editable/base.py
# SPDX-License-Identifier: Apache-2.0
"""Injected-Qt editable row-tree reads and virtual-call containment."""

from collections.abc import Callable
from functools import wraps
from time import monotonic
from typing import Any

from fontlabapp.qt.trees.data import Tree, check_deadline
from fontlabapp.qt.trees.draft import DraftTree


def emit(signal: Any, *args: Any) -> None:
    """Emit through either Qt's signal instance or PythonQt's callable signal."""
    getattr(signal, "emit", signal)(*args)


def virtual(fallback: Callable, *, write: bool = False) -> Callable:
    """Keep exceptions out of native virtuals and refuse reentrant edits."""

    def decorate(method: Callable) -> Callable:
        @wraps(method)
        def guarded(self: Any, *args: Any, **kwargs: Any) -> Any:
            if not getattr(self, "_active", False):
                return fallback()
            if write and self._editing:
                self.error = "A tree edit is already in progress."
                return fallback()
            if write:
                self._editing, self.error = True, ""
            try:
                return method(self, *args, **kwargs)
            except Exception as error:  # noqa: BLE001 - native virtual boundary
                self.error = str(error)
                return fallback()
            finally:
                if write:
                    self._editing = False
                    if self._pending_deactivate:
                        self.deactivate()

        return guarded

    return decorate


def base_type(core: Any, gui: Any = None) -> type:
    """Build against a supplied binding; no binding import or application owner."""
    qt, invalid = core.Qt, core.QModelIndex
    abstract = (core if gui is None else gui).QAbstractItemModel

    class EditableBase(abstract):
        def __init__(
            self,
            source: Tree,
            parent: Any = None,
            *,
            official: bool = False,
            deadline: float | None = None,
        ) -> None:
            limit = monotonic() + 2.0 if deadline is None else deadline
            check_deadline(limit)
            draft = DraftTree(source)
            check_deadline(limit)
            abstract.__init__(self, parent)
            self._draft, self.official, self.error = draft, official, ""
            self._editing = self._pending_deactivate = False
            self._active, self.edited = True, False

        def deactivate(self) -> None:
            """Detach views first; defer release until an edit's signals are paired."""
            if self._editing:
                self._pending_deactivate = True
                return
            self._active, self._draft = False, None

        def _identity(self, index: Any) -> int:
            if index is None or not index.isValid():
                return 0
            if index.model() != self:
                raise ValueError("Foreign tree index.")
            identity = int(index.internalId())
            if (
                identity == 0
                or index.row() != self._draft.position(identity)
                or not 0 <= index.column() < self._draft.column_count
            ):
                raise ValueError("Obsolete or mismatched tree index.")
            return identity

        @virtual(invalid)
        def node_index(self, identity: int, column: int = 0) -> Any:
            """Locate an owned occurrence after a layout change, or return invalid."""
            if identity == 0 or not 0 <= column < self._draft.column_count:
                return invalid()
            return self.createIndex(self._draft.position(identity), column, identity)

        @virtual(lambda: 0)
        def columnCount(self, parent: Any = None) -> int:
            self._identity(parent)
            return self._draft.column_count

        @virtual(lambda: 0)
        def rowCount(self, parent: Any = None) -> int:
            identity = self._identity(parent)
            if parent is not None and parent.isValid() and parent.column() != 0:
                return 0
            return len(self._draft.children(identity))

        @virtual(invalid)
        def index(self, row: int, column: int, parent: Any = None) -> Any:
            identity = self._identity(parent)
            if parent is not None and parent.isValid() and parent.column() != 0:
                return invalid()
            children = self._draft.children(identity)
            if (
                not 0 <= row < len(children)
                or not 0 <= column < self._draft.column_count
            ):
                return invalid()
            return self.createIndex(row, column, children[row])

        @virtual(invalid)
        def parent(self, index: Any) -> Any:
            identity = self._identity(index)
            parent_id = self._draft.parent(identity)
            return (
                self.createIndex(self._draft.position(parent_id), 0, parent_id)
                if parent_id
                else invalid()
            )

        @virtual(lambda: None)
        def data(self, index: Any, role: Any = qt.DisplayRole) -> object:
            if role not in (qt.DisplayRole, qt.EditRole):
                return None
            identity = self._identity(index)
            return self._draft.cells(identity)[index.column()] if identity else None

        @virtual(lambda: None)
        def headerData(
            self,
            section: int,
            orientation: Any,
            role: Any = qt.DisplayRole,
        ) -> object:
            if (
                orientation == qt.Horizontal
                and role == qt.DisplayRole
                and 0 <= section < self._draft.column_count
            ):
                return self._draft.cells(0)[section]
            return None

        @virtual(lambda: qt.NoItemFlags)
        def flags(self, index: Any) -> Any:
            return (
                qt.ItemIsEnabled | qt.ItemIsSelectable | qt.ItemIsEditable
                if self._identity(index)
                else qt.NoItemFlags
            )

    return EditableBase
