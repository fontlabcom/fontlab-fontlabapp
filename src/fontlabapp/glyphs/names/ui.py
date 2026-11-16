# this_file: src/fontlabapp/glyphs/names/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Share Names panels, complete snapshots and failure containment.

Load lazily through scripting in FontLab. Subclasses retain original controls
and calculations; these tools change only Font window selection.
"""

from functools import wraps
from typing import Any

from fontlabapp import _native
from fontlabapp.core.completion import install
from fontlabapp.core.scripting import (
    close_script_dialog,
    connect_guarded,
    current_package,
    select_glyphs,
)

QtCore, QtGui = _native("PythonQt").QtCore, _native("PythonQt").QtGui


def muted(widget: Any) -> str:
    """Return theme-derived secondary text colour."""
    color = QtGui.QColor(widget.palette.color(QtGui.QPalette.WindowText))
    color.setAlpha(150)
    return color.name(QtGui.QColor.HexArgb)


def snapshot_refresh(method: Any) -> Any:
    """Publish actions only after complete native access and result rendering."""

    @wraps(method)
    def refresh(self: Any, *args: Any, **kwargs: Any) -> Any:
        self.invalidate()
        package = current_package()
        package_id = package.id if package else None
        try:
            result = method(self, *args, **kwargs)
            if package_id is not None and current_package(package_id) is None:
                raise ValueError("Font changed during refresh; refresh again.")
            self._scanned_id = package_id
            self._snapshot_valid = package_id is not None
            if package_id is None:
                self.invalidate()
            return result
        except Exception:
            self.invalidate()
            raise

    return refresh


class NamesDialog(QtGui.QDialog):
    """Share theme, heading, owned signals, selection guards and Close cleanup."""

    def __init__(self, parent: Any, title: str, key: str) -> None:
        QtGui.QDialog.__init__(self, parent)
        self._key = key
        self._connections = []
        self._snapshot_valid = False
        self._scanned_id = None
        self.last_result = None
        self.setWindowTitle(title)
        palette = self.palette
        palette.setColor(QtGui.QPalette.Text, palette.color(QtGui.QPalette.WindowText))
        self.setPalette(palette)
        self.setMinimumWidth(480)
        self.root = QtGui.QVBoxLayout(self)
        self.root.setContentsMargins(20, 18, 20, 16)
        self.root.setSpacing(12)
        heading = QtGui.QLabel(title)
        font = heading.font
        font.setPointSizeF(font.pointSizeF() * 1.35)
        font.setBold(True)
        heading.setFont(font)
        self.root.addWidget(heading)
        self.subtitle = QtGui.QLabel()
        self.subtitle.setWordWrap(True)
        self.subtitle.setStyleSheet(f"color: {muted(self)};")
        self.root.addWidget(self.subtitle)
        self._completion_lifetime = install(self, key)

    def changeEvent(self, event: Any) -> None:
        """Refresh derived subtitle colour when the live widget palette changes."""
        QtGui.QDialog.changeEvent(self, event)
        if event.type() == QtCore.QEvent.PaletteChange:
            subtitle = getattr(self, "subtitle", None)
            if subtitle is not None:
                subtitle.setStyleSheet(f"color: {muted(self)};")

    def make_table(self, headers: list[str]) -> Any:
        """Create a shared read-only result table; tools keep column sizing."""
        table = QtGui.QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        return table

    def _connect(self, signal: Any, slot: Any) -> None:
        """Own callbacks; invalidate obsolete actions after callback failures."""

        def guarded(*args: Any) -> None:
            try:
                slot(*args)
            except Exception:
                self.invalidate()
                raise

        connect_guarded(self, signal, guarded)

    def invalidate(self) -> None:
        """Disable stale actions and clear partial results before native access."""
        self._snapshot_valid = False
        self._scanned_id = None
        self.last_result = None
        for name in ("pairs", "selection", "matches", "groups", "missing", "extra"):
            if hasattr(self, name):
                setattr(self, name, [])
        for name in ("select_button", "copy_button"):
            button = getattr(self, name, None)
            if button is not None:
                button.setEnabled(False)
        table = getattr(self, "table", None)
        if table is not None:
            table.setRowCount(0)
        for name in ("missing_list", "extra_list"):
            listing = getattr(self, name, None)
            if listing is not None:
                listing.clear()
        for field in getattr(self, "fields", {}).values():
            field.setText("–")
        self.current = {}
        specimen = getattr(self, "specimen", None)
        if specimen is not None:
            specimen.set_content(None, 0, "", (-250, 750))

    def ensure_snapshot(self) -> None:
        """Reject failed scans or switched/closed fonts before selection or copy."""
        if not self._snapshot_valid or current_package(self._scanned_id) is None:
            self.invalidate()
            raise ValueError("Results are stale; refresh or reopen this tool.")

    def select_names(self, names: list[str], *, add: bool = False) -> list[str]:
        """Validate snapshot and requested names before changing selection."""
        self.ensure_snapshot()
        try:
            return select_glyphs(names, package_id=self._scanned_id, add=add)
        except Exception:
            self.invalidate()
            raise

    def closeEvent(self, event: Any) -> None:
        """Stop owned polling, disconnect callbacks and defer destruction."""
        timer = getattr(self, "timer", None)
        close_script_dialog(self, event, self._key, timers=(timer,) if timer else ())
