# this_file: src/fontlabapp/kerning/edit/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Bind all seven kerning editors to complete previews and owned native lifecycle."""

from functools import wraps
from typing import Any

from fontlabapp.kerning.inspect.ui import KerningDialog, QtGui
from fontlabapp.kerning.batch import (
    ensure_snapshot,
    snapshot_kerning,
    validate_pair,
    write_kerning,
)


def editor_refresh(method: Any) -> Any:
    """Capture before/after the complete preview; failed reads leave Refresh available."""

    @wraps(method)
    def refresh(self: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            if self.package is None:
                result = method(self, *args, **kwargs)
                self.invalidate()
                return result
            before = snapshot_kerning(self.package)
            if list(before.masters) != self.masters:
                raise ValueError("Masters changed; reopen this tool.")
            result = method(self, *args, **kwargs)
            ensure_snapshot(self.package, before)
            self._kerning_snapshot = before
            self._snapshot_valid, self._scanned_id = True, before.package_id
            button = getattr(self, "add_button", None)
            if button is not None:
                button.setEnabled(bool(getattr(self, "glyph", None)))
            return result
        except Exception as error:  # noqa: BLE001 - preserve native Undo / contain UI callbacks
            self.invalidate()
            self.status.setText(f"Error: {error} Use Refresh to scan again.")
            self.slot_error = repr(error)
            return None

    return refresh


def editor_apply(method: Any) -> Any:
    """Refuse stale rows; preserve completed writes across later display failures."""

    @wraps(method)
    def apply(self: Any, *args: Any, **kwargs: Any) -> Any:
        self._batch_written = False
        try:
            self.ensure_edit_snapshot()
            return method(self, *args, **kwargs)
        except Exception as error:
            completed = self._batch_written
            self.invalidate()
            if completed:
                raise RuntimeError(
                    "Kerning was applied, but the display or preview failed; "
                    f"use Undo to restore it or Refresh to scan again. {error}"
                ) from error
            raise

    return apply


class KerningEditDialog(KerningDialog):
    """Reuse the established shell/Close ownership and add a real Refresh action."""

    def __init__(self, parent: Any, title: str, key: str) -> None:
        """Bind to the current package; no font data or active master is changed."""
        super().__init__(parent, title, key)
        self._kerning_snapshot = None
        self.errors = {}

    def add_refresh(self, footer: Any, callback: Any) -> None:
        """Add a visible recovery action and keep long diagnostics inside the panel."""
        self.status.setWordWrap(True)
        self.refresh_button = QtGui.QPushButton("Refresh")
        footer.insertWidget(1, self.refresh_button)
        self._connect(self.refresh_button.clicked, lambda *args: callback())

    def ensure_edit_snapshot(self) -> None:
        """Check complete pairs/classes/master membership and current original font."""
        if not self._snapshot_valid or self._kerning_snapshot is None:
            raise ValueError("Kerning results are stale; use Refresh before applying.")
        ensure_snapshot(self.package, self._kerning_snapshot)

    def write_edits(self, edits: dict, title: str) -> bool:
        """Pass exactly the displayed baseline to the complete multi-master writer."""
        self._batch_written = write_kerning(
            self.package, edits, title, expected=self._kerning_snapshot
        )
        return self._batch_written

    def refresh_after_apply(self, callback: Any) -> None:
        """Keep post-write read failures honest; never replace them with success counts."""
        callback()
        if not self._snapshot_valid:
            outcome = (
                "Kerning was applied"
                if self._batch_written
                else "No changes were required"
            )
            raise RuntimeError(
                f"{outcome}, but the preview failed; use Refresh. {getattr(self, 'slot_error', '')}"
            )

    def refresh_values(self) -> None:
        """Share the Scale/Round complete preview rendering lazily."""
        from fontlabapp.kerning.edit.values_ui import refresh_values

        refresh_values(self)

    def apply_values(self, title: str) -> None:
        """Share the Scale/Round batch write, refreshed preview and count footer."""
        from fontlabapp.kerning.edit.values_ui import apply_values

        apply_values(self, title)

    def stage_editor_cell(
        self, pair: tuple[str, str], master: str, text: str, old: float | None
    ) -> str | None:
        """Stage one valid cell; keep other edits and return useful invalid-input feedback."""
        from fontlabapp.kerning.edit.model import stage_cell

        key = pair, master
        try:
            validate_pair(self.package, master, pair)
        except ValueError as error:
            self.staged.pop(key, None)
            self.errors[key] = text
            return str(error)
        if not stage_cell(self.staged, self.errors, key, text, old):
            return f"“{text}” is not a valid kerning value; other valid edits remain staged"
        return None

    def invalidate(self) -> None:
        """Remove partial staging/results and disable mutation until a complete Refresh."""
        self.filling = True
        super().invalidate()
        self._kerning_snapshot = None
        self.last_result = None
        self.rows, self.staged, self.errors, self.todo, self.found = {}, {}, {}, {}, {}
        self.order = []
        self.values = {}
        if isinstance(getattr(self, "pairs", None), list):
            self.pairs = []
        for name in ("apply_button", "revert_button", "add_button"):
            button = getattr(self, name, None)
            if button is not None:
                button.setEnabled(False)
        targets = getattr(self, "targets", None)
        if targets is not None:
            targets.setRowCount(0)
        self.filling = False


def make_table(headers: list[str]) -> Any:
    """Build the shared original preview table, including checkable-row editors."""
    from fontlabapp.glyphs.names.ui import QtCore

    table = QtGui.QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
    table.setSelectionMode(QtGui.QAbstractItemView.NoSelection)
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    header = table.horizontalHeader()
    header.setSectionResizeMode(QtGui.QHeaderView.Stretch)
    header.setSectionResizeMode(0, QtGui.QHeaderView.ResizeToContents)
    table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
    table.setMinimumHeight(220)
    return table
