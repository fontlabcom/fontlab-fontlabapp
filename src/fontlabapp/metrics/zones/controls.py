# this_file: src/fontlabapp/metrics/zones/controls.py
# SPDX-License-Identifier: Apache-2.0
"""Keep original alignment-zone controls and table rendering in the shared App."""

import sys
from typing import Any

import fontlabapp.qt.properties as _qt_properties
from fontlabapp.glyphs.names.ui import QtCore, QtGui, muted


def value(widget: Any, name: str) -> Any:
    """Read a PythonQt property or the equivalent offscreen Qt test accessor."""
    return _qt_properties.value(widget, name)


def build(dialog: Any) -> None:
    """Create every control and Close before any fallible source access."""
    dialog.setModal(False)
    dialog._row_origins = ()
    dialog.resize(680, 460)
    dialog.setMinimumWidth(560)
    dialog.subtitle.setText(
        "PostScript alignment zones per master. Top zones extend up from their position, bottom zones down."
    )
    form = QtGui.QHBoxLayout()
    form.addWidget(QtGui.QLabel("Master"))
    dialog.master = QtGui.QComboBox()
    form.addWidget(dialog.master, 1)
    dialog.suggest_button = QtGui.QPushButton("Suggest from o / O")
    form.addWidget(dialog.suggest_button)
    dialog.root.addLayout(form)
    dialog.table = QtGui.QTableWidget(0, 4)
    dialog.table.setHorizontalHeaderLabels(["Zone", "Position", "Width", "Name"])
    dialog.table.verticalHeader().setVisible(False)
    dialog.table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
    dialog.table.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
    dialog.table.setAlternatingRowColors(True)
    dialog.table.setShowGrid(False)
    dialog.table.horizontalHeader().setSectionResizeMode(QtGui.QHeaderView.Stretch)
    dialog.table.horizontalHeader().setSectionResizeMode(
        0, QtGui.QHeaderView.ResizeToContents
    )
    dialog.table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
    dialog.table.setMinimumHeight(200)
    dialog.root.addWidget(dialog.table, 1)
    edits = QtGui.QHBoxLayout()
    for name, title in (
        ("add_top", "Add top zone"),
        ("add_bottom", "Add bottom zone"),
        ("remove_button", "Remove selected"),
    ):
        button = QtGui.QPushButton(title)
        setattr(dialog, name, button)
        edits.addWidget(button)
    edits.addStretch(1)
    dialog.root.addLayout(edits)
    footer = QtGui.QHBoxLayout()
    dialog.status = QtGui.QLabel()
    dialog.status.setWordWrap(True)
    dialog.status.setStyleSheet(f"color: {muted(dialog)};")
    footer.addWidget(dialog.status, 1)
    dialog.close_button = QtGui.QPushButton("Close")
    dialog.apply_button = QtGui.QPushButton("Apply")
    dialog.apply_button.setDefault(True)
    footer.addWidget(dialog.close_button)
    footer.addWidget(dialog.apply_button)
    dialog.root.addLayout(footer)


def rows(table: Any) -> tuple[tuple[str, ...], ...]:
    """Copy all cell text before parsing; never retain native item wrappers."""
    return tuple(
        tuple(
            table.item(row, column).text()
            if table.item(row, column) is not None
            else ""
            for column in range(4)
        )
        for row in range(value(table, "rowCount"))
    )


def fill(dialog: Any) -> None:
    """Render one whole stage under a finally-restored signal recursion fence."""
    dialog._filling = True
    try:
        data = dialog.editor.rows(dialog._current)
        dialog._row_origins = dialog.editor.origins(dialog._current)
        dialog.table.setRowCount(len(data))
        for row, cells in enumerate(data):
            for column, text in enumerate(cells):
                item = QtGui.QTableWidgetItem()
                item.setData(QtCore.Qt.DisplayRole, text)
                if column in (1, 2):
                    item.setTextAlignment(
                        int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                    )
                dialog.table.setItem(row, column, item)
    finally:
        dialog._filling = False
    status(dialog)


def enabled(dialog: Any, available: bool) -> None:
    """Keep Close usable while disabling all source-dependent editing controls."""
    for control in (
        dialog.master,
        dialog.table,
        dialog.add_top,
        dialog.add_bottom,
        dialog.remove_button,
        dialog.suggest_button,
        dialog.apply_button,
    ):
        control.setEnabled(available)


def status(dialog: Any) -> None:
    """Retain original zone count and ordered dirty-master feedback."""
    pending = dialog.editor.pending()
    count = len(dialog.editor.rows(dialog._current))
    note = " · unsaved: " + ", ".join(pending) if pending else ""
    dialog.status.setText(
        f"{dialog._current}: {count} zone{'s' if count != 1 else ''}{note}"
    )
    dialog.apply_button.setEnabled(bool(pending))
    dialog.remove_button.setEnabled(count > 0)


def dispose(dialog: Any, *, destroyed: bool = False) -> None:
    """Release owned callbacks/data on Close, completion or native destruction."""
    dialog._closed = True
    dialog.editor = dialog._backend = None
    dialog._row_origins = ()
    # Qt already removes the dying emitter's own signal connections.
    if destroyed:
        dialog._connections = [
            entry
            for entry in dialog._connections
            if all(entry is not terminal for terminal in dialog._terminal_connections)
        ]
    dialog._terminal_connections.clear()
    for signal, slot in reversed(tuple(dialog._connections)):
        try:
            signal.disconnect(slot)
        except Exception as error:  # noqa: BLE001 - attempt every owned disconnect
            dialog._disconnect_errors.append(repr(error))
    dialog._connections.clear()
    windows = getattr(sys, "_fontlab_samples", {})
    if windows.get(dialog.KEY) is dialog:
        windows.pop(dialog.KEY)


def complete(dialog: Any) -> None:
    """Reject/Accept/Done hide a QDialog; also release and defer owned deletion."""
    dispose(dialog)
    dialog.deleteLater()
