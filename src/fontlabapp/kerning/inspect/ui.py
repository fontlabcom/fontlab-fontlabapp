# this_file: src/fontlabapp/kerning/inspect/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Own five read-only kerning panels with complete snapshots and safe teardown.

Reuse the Names panel's native theme, signals and validated Font window selection.
No imports of Fontport or optional UI packages are needed for native inspection.
"""

from functools import wraps
from typing import Any

from fontlabapp.glyphs.names.ui import NamesDialog, QtGui
from fontlabapp.core.scripting import close_script_dialog, current_package


def snapshot_refresh(method: Any) -> Any:
    """Clear partial results on failures; bind completed rows to the scanned font."""

    @wraps(method)
    def refresh(self: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            if self.package is not None and current_package(self.package.id) is None:
                raise ValueError(
                    "The original font is no longer current; reopen this tool."
                )
            result = method(self, *args, **kwargs)
            if self.package is not None and current_package(self.package.id) is None:
                raise ValueError("Font changed during refresh; reopen this tool.")
            self._scanned_id = self.package.id if self.package is not None else None
            self._snapshot_valid = self._scanned_id is not None
            return result
        except Exception:
            self.invalidate()
            raise

    return refresh


class KerningDialog(NamesDialog):
    """Share native panel shell and invalidate all kerning actions atomically."""

    def __init__(self, parent: Any, title: str, key: str) -> None:
        super().__init__(parent, title, key)
        self.setMinimumWidth(520)
        self.resize(760, 600)
        self.file_dialog = None
        self.package = current_package()
        self.masters = list(self.package.masters) if self.package is not None else []
        self.current_master = self.package.master if self.package is not None else ""
        ink = self.palette.color(QtGui.QPalette.WindowText).name()
        self.setStyleSheet(f"QAbstractSpinBox, QAbstractItemView {{ color: {ink}; }}")

    def invalidate(self) -> None:
        """Clear partial native/table/proof state and refuse every outgoing action."""
        self._snapshot_valid, self._scanned_id = False, None
        for name in ("rows", "shown", "names", "lefts", "rights", "missing"):
            if hasattr(self, name):
                setattr(self, name, [])
        self.paths, self.pair_rows, self.classes = {}, {}, {}
        self.selected = None
        if hasattr(self, "pairs") and isinstance(self.pairs, dict):
            self.pairs = {}
        for name in ("select_button", "export_button", "copy_button"):
            button = getattr(self, name, None)
            if button is not None:
                button.setEnabled(False)
        for name in ("table", "pairs"):
            table = getattr(self, name, None)
            if hasattr(table, "setRowCount"):
                table.setRowCount(0)
        listing = getattr(self, "list", None)
        if listing is not None:
            listing.clear()
        for name in ("title", "members"):
            label = getattr(self, name, None)
            if label is not None:
                label.setText("")
        canvas = getattr(self, "canvas", None)
        if canvas is not None:
            canvas.update()

    def closeEvent(self, event: Any) -> None:
        """Disconnect before deleting the owned chooser and proof dialog."""
        self.paths = {}
        child = self.file_dialog
        close_script_dialog(self, event, self._key, children=(child,) if child else ())
