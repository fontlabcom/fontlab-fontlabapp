# this_file: src/fontlabapp/anchors/copy/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Complete copy-panel source guards on the existing owned Masters lifecycle."""

from functools import wraps
from typing import Any

from fontlabapp.masters.inspect.ui import MastersDialog, QtCore, QtGui
from fontlabapp.anchors.copy.model import ORIGIN_ERROR, source_values
from fontlabapp.anchors.inspect.model import font_glyph_names, selected_glyphs
from fontlabapp.guides.inspect.model import affected_auto_layers, dependency_values


def snapshot_refresh(method: Any) -> Any:
    """Validate the old display before adopting intended source/control changes."""

    @wraps(method)
    def refresh(self: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            self.prepare_initial()
            self.check_binding()
            if self._snapshot_valid:
                self.ensure_snapshot(options=False)
            self._snapshot_valid = False
            self._source_names = list(
                dict.fromkeys(
                    self._selected_names
                    + (
                        [self.source.text.strip()]
                        if self.source_glyph() is not None
                        else []
                    )
                )
            )
            before, options = self.source_values(), self.option_values()
            result = method(self, *args, **kwargs)
            self.check_binding()
            if before != self.source_values() or options != self.option_values():
                raise ValueError("Source changed during preview; reopen this tool.")
            self._source, self._options = before, options
            self._display_masters, self._display_master = (
                tuple(self.masters),
                self.current_master,
            )
            self._snapshot_valid = self.package is not None
            self._scanned_id = self._bound_id
            self.last_error = ""
            return result
        except Exception:
            self.invalidate()
            raise

    return refresh


class CopyDialog(MastersDialog):
    """Retain fontwide completion separately from captured destination selection."""

    ACTION = "Copy"

    def load_initial(self) -> None:
        """Read native sources only once every control and Close already exists."""
        self.glyphs = selected_glyphs(self.package) if self.package is not None else []
        self._selected_names = [g.name for g in self.glyphs]
        self.names = font_glyph_names() if self.package is not None else []
        self.masters = list(self.package.masters) if self.package is not None else []
        self.current_master = self.package.master if self.package is not None else ""
        self.scope.setItemText(0, f"Current master ({self.current_master})")
        self.scope.setItemText(1, f"All masters ({len(self.masters)})")
        self.completion_model.setStringList(self.names)

    def clear_initial_state(self) -> None:
        """Discard wrappers and completion data after incomplete reads or Close."""
        super().clear_initial_state()
        self.glyphs, self._selected_names, self._source_names = [], [], []
        self._options, self.last_result = None, None
        self.pending_targets, self.rebuilds = set(), []
        self.pending_origins = []
        model = getattr(self, "completion_model", None)
        if model is not None:
            model.setStringList([])

    def option_values(self) -> tuple:
        """Capture every control that drives the original anchor plan."""
        return (
            self.source.text,
            self.mode.currentIndex,
            self.scale.isChecked(),
            self.scope.currentIndex,
        )

    def source_values(self, *, cached: bool = False) -> Any:
        """Bind exact membership, selection, master domain, widths and raw pins."""
        if self.package is None:
            return None
        if font_glyph_names() != self.names:
            raise ValueError("Font glyph order changed; reopen this tool.")
        if [g.name for g in selected_glyphs(self.package)] != self._selected_names:
            raise ValueError("Selection changed; reopen this tool.")
        return (
            (tuple(self.package.masters), self.package.master),
            source_values(self.package, self._source_names, self.masters),
        )

    def ensure_snapshot(self, *, options: bool = True) -> None:
        """Reject stale writes while permitting deliberate controls during refresh."""
        try:
            super().ensure_snapshot()
            if options and self.option_values() != self._options:
                raise ValueError("Options changed since preview; refresh this tool.")
        except Exception:
            self.invalidate()
            raise

    def guard_apply(self) -> None:
        """Name unsafe dependants and refuse the whole batch before native history."""
        self.rebuilds = (
            affected_auto_layers(dependency_values(self.package), self.pending_targets)
            if self.package is not None
            else []
        )
        self.rebuild_label.setText(
            "Cannot safely undo changes to automatic dependants: "
            + ", ".join(self.rebuilds)
            if self.rebuilds
            else ""
        )
        self.rebuild_label.setVisible(bool(self.rebuilds))
        if self.rebuilds:
            self.apply_button.setEnabled(False)
            self.status.setText("Copy unavailable")
        if self.pending_origins:
            self.apply_button.setEnabled(False)
            self.rebuild_label.setText(ORIGIN_ERROR)
            self.rebuild_label.setVisible(True)
            self.status.setText("Copy unavailable")
        if self.rebuilds or self.pending_origins:
            self.adjustSize()

    def invalidate(self) -> None:
        """Clear failed previews, native handles, results and dynamic completion."""
        super().invalidate()
        self.rebuild_label.setText("")
        self.rebuild_label.setVisible(False)
        self.subtitle.setText("Reopen this tool to read the current source.")

    def fill_rows(self, rows: list) -> None:
        """Retain original numeric alignment and highlighted New column."""
        ink = QtGui.QBrush(QtGui.QColor(self.palette.color(QtGui.QPalette.WindowText)))
        accent = QtGui.QBrush(QtGui.QColor(self.palette.color(QtGui.QPalette.Link)))
        self.table.setRowCount(len(rows))
        for row, (cells, changed) in enumerate(rows):
            for column, text in enumerate(cells):
                item = QtGui.QTableWidgetItem(str(text))
                item.setForeground(ink)
                if column >= 2:
                    item.setTextAlignment(
                        int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                    )
                if changed and column == 3:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    item.setForeground(accent)
                self.table.setItem(row, column, item)
