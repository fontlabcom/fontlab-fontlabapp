# this_file: src/fontlabapp/qt/tables/filter/controls.py
# SPDX-License-Identifier: Apache-2.0
"""Own every source/proxy filter control; generic three-column table UI."""

from typing import Any

import fontlabapp.qt.properties as _qt_properties
from fontlabapp.glyphs.names.ui import QtCore, QtGui


def value(widget: Any, name: str) -> Any:
    """Read only a specified Qt property or equivalent standalone accessor."""
    return _qt_properties.value(widget, name)


def view(dialog: Any, title: str) -> Any:
    group = QtGui.QWidget()
    layout = QtGui.QVBoxLayout(group)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    layout.addWidget(QtGui.QLabel(title))
    table = QtGui.QTreeView()
    table.setRootIsDecorated(False)
    table.setAlternatingRowColors(True)
    table.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
    layout.addWidget(table)
    dialog.root.addWidget(group, 1)
    return table


def build(dialog: Any, custom: bool, official: bool = False) -> None:
    """Build Close and all controls before the first fallible capture."""
    dialog.setModal(False)
    dialog.resize(640, 600)
    dialog.setMinimumSize(560, 460)
    dialog.root.setContentsMargins(12, 10, 12, 10)
    dialog.root.setSpacing(6)
    dialog.source_view = view(dialog, "Source snapshot")
    form = QtGui.QFormLayout()
    form.setContentsMargins(0, 0, 0, 0)
    form.setVerticalSpacing(6)
    form.setHorizontalSpacing(8)
    dialog.pattern = QtGui.QLineEdit()
    dialog.syntax = QtGui.QComboBox()
    dialog.syntax.addItems(["Regular expression", "Wildcard", "Fixed string"])
    dialog.column = QtGui.QComboBox()
    dialog.column.addItems(["Column 1", "Column 2", "Column 3"])
    dialog.column.setEnabled(not custom)
    if custom:
        dialog.column.setToolTip(
            "Custom searches both of the first two columns. Date limits apply to the third column."
        )
    dialog.filter_case = QtGui.QCheckBox("Case-sensitive filter")
    dialog.sort_case = QtGui.QCheckBox("Case-sensitive sorting")
    pattern = QtGui.QHBoxLayout()
    pattern.setSpacing(6)
    pattern.addWidget(dialog.pattern, 1)
    syntax_label = QtGui.QLabel("Syntax")
    syntax_label.setBuddy(dialog.syntax)
    pattern.addWidget(syntax_label)
    pattern.addWidget(dialog.syntax)
    pattern_label = QtGui.QLabel("Pattern")
    pattern_label.setBuddy(dialog.pattern)
    form.addRow(pattern_label, pattern)
    options = QtGui.QHBoxLayout()
    options.setSpacing(6)
    column_label = QtGui.QLabel("Filter column")
    column_label.setBuddy(dialog.column)
    for control in (column_label, dialog.column, dialog.filter_case, dialog.sort_case):
        options.addWidget(control)
    options.addStretch(1)
    form.addRow(options)
    if custom:
        dates = QtGui.QHBoxLayout()
        dates.setSpacing(6)
        dialog.limit_dates = QtGui.QCheckBox("Limit dates")
        dialog.limit_dates.setToolTip("Apply inclusive date limits to the third column.")
        dates.addWidget(dialog.limit_dates)
        for name, label in (("date_from", "From"), ("date_to", "To")):  # not lower/upper: QWidget slots
            editor = QtGui.QDateEdit()
            editor.setDateRange(QtCore.QDate(1, 1, 1), QtCore.QDate(9999, 12, 31))
            editor.setDisplayFormat("yyyy-MM-dd")
            editor.setCalendarPopup(True)
            editor.setSizePolicy(QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Fixed)
            setattr(dialog, name, editor)
            date_label = QtGui.QLabel(label)
            date_label.setBuddy(editor)
            dates.addWidget(date_label)
            dates.addWidget(editor)
        dates.addStretch(1)
        form.addRow(dates)
    if official:
        dialog.filter_case.setChecked(True)
        dialog.sort_case.setChecked(True)
        dialog.column.setCurrentIndex(1)
        if custom:
            dialog.column.hide()
            column_label.hide()
            dialog.sort_case.hide()
    dialog.root.addLayout(form)
    dialog.proxy_view = view(dialog, "Sorted and filtered snapshot")
    dialog.proxy_view.setSortingEnabled(True)
    if official:
        dialog.proxy_view.sortByColumn(1, QtCore.Qt.AscendingOrder)
    footer = QtGui.QHBoxLayout()
    dialog.status = QtGui.QLabel()
    dialog.status.setWordWrap(True)
    dialog.refresh_button = QtGui.QPushButton("Refresh")
    dialog.close_button = QtGui.QPushButton("Close")
    footer.addWidget(dialog.status, 1)
    footer.addWidget(dialog.refresh_button)
    footer.addWidget(dialog.close_button)
    dialog.root.addLayout(footer)
    signals = [
        dialog.pattern.textChanged,
        dialog.syntax.currentIndexChanged,
        dialog.column.currentIndexChanged,
        dialog.filter_case.toggled,
        dialog.sort_case.toggled,
    ]
    if custom:
        signals.extend(
            [
                dialog.date_from.dateChanged,
                dialog.date_to.dateChanged,
                dialog.limit_dates.toggled,
            ]
        )
    for signal in signals:
        dialog._connect(signal, lambda *args: dialog.update_filter())
    dialog._connect(dialog.refresh_button.clicked, lambda *args: dialog.refresh())
    dialog._connect(
        dialog.close_button.clicked,
        lambda *args: None if dialog._closed else dialog.close(),
    )


def populate(dialog: Any, table: Any, clock: Any) -> None:
    """Build every read-only cell before attaching either view or any proxy."""
    deadline = clock() + 2.0
    dialog.model.setColumnCount(3)
    dialog.model.setHorizontalHeaderLabels(list(table.headers))
    dialog.model.setRowCount(len(table.rows))
    if dialog.official:
        from fontlabapp.qt.tables.filter.official import item as make_item
    else:
        make_item = lambda column, text, epoch=None: QtGui.QStandardItem(text)
    for i, row in enumerate(table.rows):
        if clock() >= deadline:
            raise TimeoutError("Table rendering expired; no partial view.")
        for column, text in enumerate(row):
            item = make_item(
                column, text, table.epochs[i] if table.epochs is not None else None
            )
            item.setEditable(False)
            dialog.model.setItem(i, column, item)
