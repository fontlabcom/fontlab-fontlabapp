# this_file: src/fontlabapp/guides/rewrite/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Late binding for complete guide editors on the existing owned guide shell."""

from typing import Any

from fontlabapp.guides.inspect.ui import GuidesDialog, QtGui, api


class RewriteDialog(GuidesDialog):
    """Retain source/selection safety while owning dynamic master target controls."""

    def load_initial(self) -> None:
        """Populate master controls only after the status and Close controls exist."""
        if hasattr(self, "scope"):
            super().load_initial()
            self.glyph = self.glyphs[0] if self.glyphs else None
            return
        self._scanning = False
        self.glyphs = (
            api.selected_glyphs(self.package) if self.package is not None else []
        )
        self.names = [glyph.name for glyph in self.glyphs]
        self.masters = list(self.package.masters) if self.package is not None else []
        self.current_master = self.package.master if self.package is not None else ""
        if self.target_checks and list(self.target_checks) != self.masters:
            raise ValueError("Masters changed; reopen this tool.")
        blocked = self.source.blockSignals(True)
        try:
            self.source.clear()
            self.source.addItems(self.masters)
            if self.current_master in self.masters:
                self.source.setCurrentIndex(self.masters.index(self.current_master))
        finally:
            self.source.blockSignals(blocked)
        self.source.setEnabled(bool(self.masters))
        for index, master in enumerate(self.masters):
            if master not in self.target_checks:
                check = QtGui.QCheckBox(master)
                check.setChecked(True)
                self.target_checks[master] = check
                self.targets_grid.addWidget(check, index // 3, index % 3)
                self._connect(check.toggled, lambda *a: self.refresh())

    def clear_initial_state(self) -> None:
        """Release glyph wrappers and disable master widgets after a failed read."""
        super().clear_initial_state()
        self.glyph = None
        source = getattr(self, "source", None)
        if source is not None:
            blocked = source.blockSignals(True)
            try:
                source.clear()
                source.setEnabled(False)
            finally:
                source.blockSignals(blocked)
        for check in getattr(self, "target_checks", {}).values():
            check.setEnabled(False)

    def invalidate(self) -> None:
        """Keep stale editable cells and row actions unavailable until a fresh read."""
        super().invalidate()
        if self._key == "guides_list_editor":
            self.table.setEnabled(False)
            self.add_button.setEnabled(False)
            self.delete_button.setEnabled(False)

    def option_values(self) -> Any:
        """Bind source-driving controls; table edits remain the user's proposed data."""
        if self._key == "guides_clear":
            return (
                self.scope.currentIndex,
                self.direction.currentIndex,
                self.name_filter.text,
            )
        if self._key == "guides_list_editor":
            return (self.scope.currentIndex,)
        return (
            self.source.currentText,
            self.mode.currentIndex,
            self.follow_width.isChecked(),
            tuple(
                (name, check.isChecked()) for name, check in self.target_checks.items()
            ),
        )

    def source_values(self, *, cached: bool = False) -> Any:
        """Bind copy scaling to every source/target advance shown in its plan."""
        values = super().source_values(cached=cached)
        if self._key != "guides_copy_between_masters" or self.package is None:
            return values
        widths = tuple(
            (glyph.name, master, float(layer.advanceWidth))
            for glyph in self.glyphs
            for master, layer in api.master_layers(glyph, self.masters)
        )
        return values, widths
