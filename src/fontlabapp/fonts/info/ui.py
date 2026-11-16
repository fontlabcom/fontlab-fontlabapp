# this_file: src/fontlabapp/fonts/info/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Shared Font Info panel adapted from the Apache-2.0 FontLab samples.

The six scripts retain their controls, plans and actions. This module is imported
only by scripting.font_info_dialog_type() when a Font Info tool runs. See NOTICE
and LICENSE for source provenance and license terms.
"""

from collections.abc import Callable
from typing import Any

from fontlabapp import _native
from fontlabapp.core.completion import install
from fontlabapp.core.scripting import (
    close_script_dialog,
    connect_guarded,
    current_package,
)

QtCore, QtGui = _native("PythonQt").QtCore, _native("PythonQt").QtGui


class FontInfoDialog(QtGui.QDialog):
    """The existing six-tool dialog shell with guarded preview safety methods."""

    MASTER_BOUND: bool = False

    def __init__(
        self, parent: Any = None, *, title: str, subtitle: str, key: str
    ) -> None:
        """Build the shared six-tool shell, then run subclass setup and refresh."""
        QtGui.QDialog.__init__(self, parent)
        self.package = current_package()
        self.package_id = self.package.id if self.package is not None else None
        self.preview_master = self.package.master if self.package is not None else None
        self._preview_valid = False
        self._plan = []
        self._connections = []
        self.dialog_key = key
        self.setWindowTitle(title)
        palette = self.palette
        ink = palette.color(QtGui.QPalette.WindowText)
        palette.setColor(
            QtGui.QPalette.Text,
            ink,
        )  # FontLab's Text can be light on a light Base
        self.setPalette(palette)
        self.setStyleSheet(
            f"QAbstractSpinBox, QAbstractItemView {{ color: {ink.name()} }}",
        )
        self.setMinimumWidth(700)
        root = QtGui.QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(12)
        heading = QtGui.QLabel(title)
        face = heading.font
        face.setPointSizeF(face.pointSizeF() * 1.35)
        face.setBold(True)
        heading.setFont(face)
        root.addWidget(heading)
        self.subtitle = QtGui.QLabel(
            subtitle if self.package else "Open a font, then reopen this tool.",
        )
        self.subtitle.setWordWrap(True)
        root.addWidget(self.subtitle)
        self.form = QtGui.QGridLayout()
        root.addLayout(self.form)
        self.table = QtGui.QTableWidget()
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QtGui.QAbstractItemView.NoSelection)
        self.table.setFocusPolicy(QtCore.Qt.NoFocus)
        self.table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.table.setMinimumHeight(230)
        root.addWidget(self.table, 1)
        self.content = root
        self.status = QtGui.QLabel("")
        self.status.setWordWrap(True)
        muted = QtGui.QColor(
            self.palette.color(QtGui.QPalette.WindowText),
        )  # copy before setAlpha
        muted.setAlpha(170)
        self.status.setStyleSheet("color: " + muted.name(QtGui.QColor.HexArgb))
        self.subtitle.setStyleSheet("color: " + muted.name(QtGui.QColor.HexArgb))
        footer = QtGui.QHBoxLayout()
        footer.addWidget(self.status, 1)
        self.close_button = QtGui.QPushButton("Close")
        self.close_button.setAutoDefault(False)  # keep Apply as the default button
        self.apply_button = QtGui.QPushButton("Apply")
        self.apply_button.setDefault(True)
        footer.addWidget(self.close_button)
        footer.addWidget(self.apply_button)
        root.addLayout(footer)
        self._connect(self.close_button.clicked, lambda *a: self.close())
        self._connect(self.apply_button.clicked, lambda *a: self.apply())
        self.apply_button.setEnabled(self.package is not None)
        self._completion_lifetime = install(self, key)
        self.safe(lambda: (self.setup(), self.refresh()))

    def safe(self, action: Callable[[], Any]) -> Any:
        """Contain native callback failures and invalidate unsafe previews."""
        try:
            return action()
        except Exception as error:  # noqa: BLE001 - contain native callback errors
            self._preview_valid = False
            self.status.setText(str(error))
            self.apply_button.setEnabled(False)

    def _connect(self, signal: Any, slot: Callable[..., Any]) -> None:
        """Connect an owned callback through shared error containment."""
        connect_guarded(self, signal, lambda *args: self.safe(lambda: slot(*args)))

    def ensure_font(self) -> None:
        """Resolve current font before touching the borrowed preview package."""
        active = current_package()
        if active is None or active.id != self.package_id:
            self._preview_valid = False
            raise ValueError("Activate the original font and reopen this tool.")
        self.package = active

    def ensure_preview(self) -> None:
        """Refuse Apply after failed previews, font switches or master switches."""
        self.ensure_font()
        if not self._preview_valid:
            raise ValueError("No valid preview; refresh or reopen this tool.")
        if self.MASTER_BOUND and self.package.master != self.preview_master:
            self._preview_valid = False
            raise ValueError("Master changed since preview; reopen this tool.")

    def rows(self, headings: Any, rows: Any) -> None:
        """Display complete preview rows without editing font data."""
        self.table.setColumnCount(len(headings))
        self.table.setHorizontalHeaderLabels(headings)
        self.table.setRowCount(len(rows))
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QtGui.QHeaderView.Stretch)
        header.setSectionResizeMode(0, QtGui.QHeaderView.ResizeToContents)
        for row, values in enumerate(rows):
            for column, value in enumerate(values):
                item = QtGui.QTableWidgetItem(str(value))
                if isinstance(value, (float, int)):
                    item.setTextAlignment(
                        int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter),
                    )
                self.table.setItem(row, column, item)

    def closeEvent(self, event: Any) -> None:
        """Disconnect owned slots and destroy this modeless dialog on close."""
        self._preview_valid = False
        self.package = self.package_id = self.preview_master = None
        self._plan = []
        close_script_dialog(self, event, self.dialog_key)
