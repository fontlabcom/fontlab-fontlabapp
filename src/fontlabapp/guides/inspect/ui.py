# this_file: src/fontlabapp/guides/inspect/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Late guide binding and full source guards on the existing owned Masters shell."""

from importlib import import_module
from typing import Any

from fontlabapp.masters.inspect.ui import MastersDialog, QtCore, QtGui

api = import_module("fontlabapp.guides.inspect.model")


class GuidesDialog(MastersDialog):
    """Keep selected glyphs and native preview handles within the shared lifecycle."""

    def load_initial(self) -> None:
        """Capture selection and master captions only after status and Close exist."""
        self._scanning = False
        self.glyphs = (
            api.selected_glyphs(self.package) if self.package is not None else []
        )
        self.names = [glyph.name for glyph in self.glyphs]
        self.masters = list(self.package.masters) if self.package is not None else []
        self.current_master = self.package.master if self.package is not None else ""
        self.scope.setItemText(0, f"Current master ({self.current_master})")
        self.scope.setItemText(1, f"All masters ({len(self.masters)})")

    def source_values(self, *, cached: bool = False) -> Any:
        """Reject changed selection, guide data, geometry or silently changed controls."""
        if self.package is None:
            return None
        selected = [glyph.name for glyph in api.selected_glyphs(self.package)]
        if selected != self.names:
            raise ValueError("Selection changed; reopen this tool.")
        return (
            self.option_values(),
            api.source_values(
                self.package,
                self.names,
                self.masters,
                geometry=self._key == "guides_grid_generator",
                font_guides=self._key == "guides_font_guides_panel",
            ),
        )

    def clear_initial_state(self) -> None:
        """Drop every captured glyph/layer handle along with shared master metadata."""
        super().clear_initial_state()
        self.glyphs, self.planned = [], []
        self.pending_targets, self.blocked = set(), []

    def invalidate(self) -> None:
        """Clear unsafe actions and painted native paths once, without a repaint loop."""
        super().invalidate()
        self.last_result = None
        label = getattr(self, "font_guides", None)
        if label is not None:
            label.setText("")
        self.subtitle.setText("Reopen this tool to read the current source.")
        preview = getattr(self, "preview", None)
        if preview is not None:
            populated = preview.path is not None or bool(preview.records)
            preview.path, preview.advance, preview.records = None, 0, []
            preview.frame = (-250.0, 750.0)
            if populated:
                preview.update()

    def teardown(self) -> None:
        """Release preview callbacks before the existing signal/disposal boundary."""
        preview = getattr(self, "preview", None)
        if preview is not None:
            preview.before_draw = preview.on_error = preview.failure_cleanup = None

    def guard_apply(self, count: int) -> None:
        """Keep full previews, but disable an entire unsafe write before history."""
        self.blocked = []
        if self.package is None or not count:
            return
        self.blocked = api.affected_auto_layers(
            api.dependency_values(self.package), self.pending_targets
        )
        if self.blocked:
            self.apply_button.setEnabled(False)
            shown = ", ".join(self.blocked[:8])
            if len(self.blocked) > 8:
                shown += f" +{len(self.blocked) - 8} more"
            self.status.setText(
                "Cannot safely undo changes to automatic dependants: " + shown
            )

    def check_preview(self) -> None:
        """Validate a populated preview; allow neutral, cleared no-font drawing."""
        self.check_binding()
        if self.package is not None:
            self.ensure_snapshot()

    def fill_guide_rows(
        self, rows: list, numeric: set[int], accent_column: int | None = None
    ) -> None:
        """Keep original guide counts/coordinates and add-state item styling."""
        ink = QtGui.QColor(self.palette.color(QtGui.QPalette.WindowText))
        accent = QtGui.QColor(self.palette.color(QtGui.QPalette.Link))
        self.table.setRowCount(len(rows))
        for row, cells in enumerate(rows):
            for column, text in enumerate(cells):
                item = QtGui.QTableWidgetItem(text)
                item.setForeground(
                    QtGui.QBrush(
                        accent if column == accent_column and text == "add" else ink
                    )
                )
                if column in numeric and (accent_column is not None or text.isdigit()):
                    item.setTextAlignment(
                        int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                    )
                self.table.setItem(row, column, item)

    def _spin(self, low: Any, high: Any, value: Any) -> Any:
        """Retain original guide controls, complete data and guarded native actions."""
        spin = QtGui.QSpinBox()
        spin.setRange(low, high)
        spin.setValue(value)
        spin.setSuffix(" units")
        spin.setAlignment(QtCore.Qt.AlignRight)
        return spin
