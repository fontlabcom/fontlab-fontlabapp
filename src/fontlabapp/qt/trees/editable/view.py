# this_file: src/fontlabapp/qt/trees/editable/view.py
# SPDX-License-Identifier: Apache-2.0
"""Retain row expansion while Qt remaps persistent cell columns.

The panel owns exact connections for expanded/collapsed, rowsRemoved and
layoutChanged. This helper creates none. Dispose before deleting owned widgets;
after parent destruction disposal only drops Python references.
"""

from typing import Any


class ExpandedRows:
    """Track observed row occurrences, independent of their current column."""

    def __init__(self, view: Any, model: Any) -> None:
        self.view, self.model = view, model
        self.identities: set[int] = set()
        self.error = ""
        self._closed = self._restoring = False

    def expanded(self, index: Any) -> None:
        """Remember expansion events, including expandAll's per-row events."""
        if self._closed or self._restoring:
            return
        try:
            identity = self.model._identity(index)
            if identity:
                self.identities.add(identity)
        except Exception as error:  # noqa: BLE001 - owned Qt callback boundary
            self.error = str(error)

    def collapsed(self, index: Any) -> None:
        """Forget deliberate collapses; restoration's internal collapse is ignored."""
        if self._closed or self._restoring:
            return
        try:
            self.identities.discard(self.model._identity(index))
        except Exception as error:  # noqa: BLE001 - owned Qt callback boundary
            self.error = str(error)

    def prune(self, *args: Any) -> None:
        """Forget removed subtrees so monotonically increasing IDs cannot leak."""
        if self._closed:
            return
        try:
            self.identities.intersection_update(self.model._draft.identities())
        except Exception as error:  # noqa: BLE001 - owned Qt callback boundary
            self.error = str(error)

    def restore(self, *args: Any) -> None:
        """Reapply live row expansion after a global column layout change."""
        if self._closed:
            return
        self._restoring = True
        try:
            self.prune()
            current = self.view.currentIndex()
            self.view.collapseAll()
            for identity in sorted(self.identities):
                index = self.model.node_index(identity)
                if index.isValid():
                    self.view.setExpanded(index, True)
            if current.isValid():
                self.view.setCurrentIndex(current)
        except Exception as error:  # noqa: BLE001 - owned Qt callback boundary
            self.error = str(error)
        finally:
            self._restoring = False

    def dispose(self) -> None:
        """Fence queued callbacks and release refs without native dereferences."""
        self._closed = True
        self.identities.clear()
        self.view = self.model = None
