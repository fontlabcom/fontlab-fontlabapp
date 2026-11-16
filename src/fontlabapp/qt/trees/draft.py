# this_file: src/fontlabapp/qt/trees/draft.py
# SPDX-License-Identifier: Apache-2.0
"""Local editable-tree data for the two item-model lessons; no native writers.

Stable occurrence IDs keep duplicate text distinct and never recycle removed
handles. Columns belong to the whole tree, including the zero-column state.
Qt index notifications and each lesson's menu policy belong to the adapter.
"""

from dataclasses import dataclass

from fontlabapp.qt.trees.data import Tree

MAX_CELLS = 1_000_000


@dataclass
class _Entry:
    parent: int | None
    cells: list[object]
    children: list[int]


def _range(position: int, count: int, length: int, *, inserting: bool) -> None:
    if (
        type(position) is not int
        or type(count) is not int
        or count < 1
        or not 0 <= position <= length
        or (not inserting and position + count > length)
    ):
        raise ValueError("Tree position/count is outside its range.")


def _capacity(nodes: int, columns: int) -> None:
    if nodes * max(1, columns) > MAX_CELLS:
        raise ValueError("Local tree cell limit exceeded; keep the complete draft.")


class DraftTree:
    """Copy a complete Tree into an owned draft; callers never receive lists.

    Root ID is zero. Input row N becomes node N+1. Mutation arguments are strict
    text/integers; adapters convert Qt values at their own boundary. Rejected
    edits leave all data and the next identity unchanged. A million-cell limit
    bounds accidental huge allocations, including trees with zero columns.
    """

    def __init__(self, source: Tree) -> None:
        if not isinstance(source, Tree):
            raise TypeError("Draft needs a complete Tree.")
        width = len(source.headers)
        _capacity(len(source.rows) + 1, width)
        self._nodes = {0: _Entry(None, list(source.headers), [])}
        for identity, (parent, cells) in enumerate(source.rows, 1):
            if len(cells) > width:
                raise ValueError("Tree row has more cells than headers.")
            self._nodes[identity] = _Entry(
                parent + 1, list(cells) + [""] * (width - len(cells)), []
            )
            self._nodes[parent + 1].children.append(identity)
        self._next = len(self._nodes)

    def _entry(self, identity: int) -> _Entry:
        if type(identity) is not int or identity not in self._nodes:
            raise ValueError("Unknown tree node.")
        return self._nodes[identity]

    @property
    def column_count(self) -> int:
        """Return global column count, which may be zero after removal."""
        return len(self._nodes[0].cells)

    def identities(self) -> tuple[int, ...]:
        """Return all live IDs, root first, in allocation order."""
        return tuple(self._nodes)

    def cells(self, identity: int) -> tuple[object, ...]:
        """Return an immutable copy of row cells, or headers for the root."""
        return tuple(self._entry(identity).cells)

    def children(self, identity: int) -> tuple[int, ...]:
        """Return immediate children in visible row order."""
        return tuple(self._entry(identity).children)

    def parent(self, identity: int) -> int | None:
        """Return the parent ID; only root has no parent."""
        return self._entry(identity).parent

    def position(self, identity: int) -> int:
        """Return the current sibling position, refusing the invisible root."""
        parent = self.parent(identity)
        if parent is None:
            raise ValueError("The tree root has no row position.")
        return self._nodes[parent].children.index(identity)

    def set_cell(self, identity: int, column: int, value: str) -> None:
        """Set one text cell or header; no data coercion hides invalid values."""
        if type(value) is not str:
            raise TypeError("Tree cells must be text.")
        self.set_value(identity, column, value)

    def set_value(self, identity: int, column: int, value: object) -> None:
        """Retain an edited QVariant value for the official example's policy.

        This explicit boundary preserves None, numeric and Qt value objects;
        set_cell remains the strict text API. Values are stored by reference,
        as in the original item model. No conversion or host access occurs.
        """
        entry = self._entry(identity)
        _range(column, 1, self.column_count, inserting=False)
        entry.cells[column] = value

    def fork(self) -> "DraftTree":
        """Copy containers for complete edit preflight before Qt notifications.

        Opaque cell values retain their identity; they are never deep-copied or
        executed. Changing either copy's cells/structure leaves the other alone.
        """
        result = object.__new__(DraftTree)
        result._nodes = {
            i: _Entry(entry.parent, list(entry.cells), list(entry.children))
            for i, entry in self._nodes.items()
        }
        result._next = self._next
        return result

    def insert_rows(
        self, parent: int, position: int, count: int, cells: tuple[str, ...]
    ) -> tuple[int, ...]:
        """Insert independent equal rows; return their fresh occurrence IDs."""
        entry = self._entry(parent)
        _range(position, count, len(entry.children), inserting=True)
        _capacity(len(self._nodes) + count, self.column_count)
        if (
            type(cells) is not tuple
            or len(cells) != self.column_count
            or any(type(cell) is not str for cell in cells)
        ):
            raise TypeError("New rows need an exact tuple of text columns.")
        ids = tuple(range(self._next, self._next + count))
        additions = {i: _Entry(parent, list(cells), []) for i in ids}
        siblings = entry.children[:position] + list(ids) + entry.children[position:]
        self._nodes.update(additions)
        entry.children = siblings
        self._next += count
        return ids

    def remove_rows(self, parent: int, position: int, count: int) -> tuple[int, ...]:
        """Remove rows and complete descendant subtrees without recursion."""
        entry = self._entry(parent)
        _range(position, count, len(entry.children), inserting=False)
        pending = list(reversed(entry.children[position : position + count]))
        removed = []
        while pending:
            identity = pending.pop()
            removed.append(identity)
            pending.extend(reversed(self._nodes[identity].children))
        del entry.children[position : position + count]
        for identity in removed:
            del self._nodes[identity]
        return tuple(removed)

    def insert_columns(self, position: int, count: int, header: str = "Column") -> None:
        """Insert global columns while preserving hierarchy and node IDs."""
        _range(position, count, self.column_count, inserting=True)
        _capacity(len(self._nodes), self.column_count + count)
        if type(header) is not str:
            raise TypeError("Tree headers must be text.")
        updates = {
            i: entry.cells[:position]
            + [header if i == 0 else ""] * count
            + entry.cells[position:]
            for i, entry in self._nodes.items()
        }
        for identity, cells in updates.items():
            self._nodes[identity].cells = cells

    def remove_columns(self, position: int, count: int) -> None:
        """Remove global columns; callers choose whether to drop empty rows."""
        _range(position, count, self.column_count, inserting=False)
        updates = {
            i: entry.cells[:position] + entry.cells[position + count :]
            for i, entry in self._nodes.items()
        }
        for identity, cells in updates.items():
            self._nodes[identity].cells = cells
