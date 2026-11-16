# this_file: src/fontlabapp/studios/vertical_metrics/_shared.py
# SPDX-License-Identifier: Apache-2.0
"""Pieces shared by the Vertical Metrics & Zones tabs: backends, labels, master tables, native names.

What: ``backends()`` is ``core.scripting.vertical_metrics_backends()`` (tests
replace it); ``label(action, masters)`` is the one Undo label form
``"Vertical Metrics: <action> of <masters>"``; ``MasterTable`` is a plain
Qt table with one row per master (zones, metrics and angles are master
data, not glyph layers, so ``GlyphTable`` rows do not fit); ``ap``/
``fontlab`` resolve the native modules on first attribute use, so the
verbatim Scriptmix functions keep their ``ap.FL``/``ap.fontlab``/``fontlab``
reads while the package imports offline.
Used by every tab module of ``fontlabapp.studios.vertical_metrics``.
"""

import importlib
from collections.abc import Callable, Iterable
from types import SimpleNamespace
from typing import Any

from PythonQt import QtCore, QtGui

from fontlabapp.core.scripting import vertical_metrics_backends

from .._kerning_ui import SortItem
from . import LABEL


class NativeModule:
    """A native module looked up on each attribute read (offline imports stay native-free)."""

    def __init__(self, name: str) -> None:
        self.name = name

    def __getattr__(self, attribute: str) -> Any:
        if attribute.startswith("__"):
            raise AttributeError(attribute)
        return getattr(importlib.import_module(self.name), attribute)


#: ``fly.ap`` as the Scriptmix functions read it: ``ap.FL`` and ``ap.fontlab``.
fontlab = NativeModule("fontlab")
ap = SimpleNamespace(FL=NativeModule("FL"), fontlab=fontlab)


def backends() -> Any:
    """The reused App backends (``core.scripting.vertical_metrics_backends``)."""
    return vertical_metrics_backends()


def plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def keep(panel: Any, slot: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap an edit slot: a refusal goes to the status line and the tab keeps what it shows.

    ``Panel.contain`` clears the tab on an error, which suits a failed read
    but would drop staged edits on one bad cell; edit slots use this instead.
    """
    return lambda *args: panel.run(lambda: slot(*args))


def label(action: str, masters: Iterable[str]) -> str:
    """``"Vertical Metrics: set metrics of Regular, Bold"``: the Undo step name of one Apply."""
    return f"{LABEL}: {action} of {', '.join(dict.fromkeys(masters))}"


class MasterTable:
    """A plain table, one row per master (or per master and field); ``cell`` reads edited text."""

    def __init__(
        self,
        owner: Any,
        layout: Any,
        columns: list[str],
        *,
        editable: tuple[int, ...] = (),
        changed: Callable[[], Any] | None = None,
        chosen: Callable[[str], Any] | None = None,
    ) -> None:
        self.view = QtGui.QTableWidget(0, len(columns), owner)
        self.view.setHorizontalHeaderLabels(columns)
        self.view.setAccessibleName(columns[0])
        self.view.horizontalHeader().setStretchLastSection(True)
        self.view.horizontalHeader().setSectionResizeMode(QtGui.QHeaderView.Interactive)
        self.view.setSortingEnabled(True)
        self.view.sortItems(0, QtCore.Qt.AscendingOrder)
        self.view.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        layout.addWidget(self.view, 1)
        self.editable = editable
        self.keys: list[str] = []
        self.filling = False
        if changed is not None:
            self.view.itemChanged.connect(
                lambda *args: None if self.filling else changed()
            )
        if chosen is not None:
            self.view.itemSelectionChanged.connect(lambda *args: self._chosen(chosen))

    def _chosen(self, slot: Callable[[str], Any]) -> None:
        rows = self.selected()
        if rows and 0 <= rows[0] < len(self.keys):
            slot(self.keys[rows[0]])

    def set_rows(self, rows: list[tuple], keys: list[str] | None = None) -> None:
        """Show ``rows``; ``keys`` names each row (the master) for selection callbacks."""
        selected = {(self.keys[index], index) for index in self.selected()}
        self.filling = True
        self.view.setSortingEnabled(False)
        self.keys = list(keys) if keys is not None else [str(r[0]) for r in rows]
        self.view.setRowCount(0)
        for number, values in enumerate(rows):
            self.view.insertRow(number)
            for column, value in enumerate(values):
                item = SortItem(str(value))
                item.setData(QtCore.Qt.UserRole, number)
                flags = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
                if column in self.editable:
                    flags |= QtCore.Qt.ItemIsEditable
                item.setFlags(flags)
                self.view.setItem(number, column, item)
        self.view.setSortingEnabled(True)
        for number, key in enumerate(self.keys):
            if (key, number) in selected:
                self.select(number)
        self.filling = False

    def visual_row(self, number: int) -> int:
        return next((row for row in range(self.count())
                     if self.view.item(row, 0).data(QtCore.Qt.UserRole) == number), -1)

    def count(self) -> int:
        rows: Any = self.view.rowCount
        return rows() if callable(rows) else rows

    def cell(self, number: int, column: int) -> str:
        item = self.view.item(self.visual_row(number), column)
        return "" if item is None else item.text()

    def set_cell(self, number: int, column: int, text: str) -> None:
        """Type ``text`` into one cell, as an edit by the user (tests and Suggest)."""
        self.view.item(self.visual_row(number), column).setText(text)

    def selected(self) -> list[int]:
        return sorted(
            {int(self.view.item(index.row(), 0).data(QtCore.Qt.UserRole))
             for index in self.view.selectionModel().selectedRows(0)}
        )

    def select(self, number: int) -> None:
        self.view.selectRow(self.visual_row(number))


__all__ = [
    "MasterTable",
    "NativeModule",
    "ap",
    "backends",
    "fontlab",
    "keep",
    "label",
    "plural",
]
