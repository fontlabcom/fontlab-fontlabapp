# this_file: src/fontlabapp/glyphs/tree/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Owned read-only tree lesson panels; metadata and models are complete or absent."""

import sys
from collections.abc import Callable
from time import monotonic
from typing import Any

from fontlabapp.glyphs.names.ui import NamesDialog, QtCore, QtGui
from fontlabapp.qt.trees.readonly import model_type
from fontlabapp.qt.trees.data import Tree, check_deadline

TreeModel = model_type(QtCore)


class GlyphTreeDialog(NamesDialog):
    """Own one view/model/selection pair and every connection until completion."""

    def __init__(
        self,
        parent: Any,
        title: str,
        key: str,
        capture: Callable[..., Tree],
        outline: bool,
    ) -> None:
        super().__init__(parent, title, key)
        self.KEY, self._capture, self.outline = key, capture, outline
        self._closed, self.model, self._selection = False, None, None
        self._selection_connections, self._disconnect_errors = [], []
        self.subtitle.setText(
            "Expand each glyph to inspect every Unicode assignment and its local modification date. Refresh reads the current font again. This snapshot is read-only."
        )
        self.view = QtGui.QTreeView(self)
        self.view.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
        self.view.setAlternatingRowColors(True)
        self.view.setUniformRowHeights(True)
        self.view.setSelectionBehavior(QtGui.QAbstractItemView.SelectItems)
        self.view.header().setStretchLastSection(True)
        self.exit_action = None
        if outline:
            self.menu_bar = QtGui.QMenuBar(self)
            self.menu_bar.setNativeMenuBar(False)
            self.exit_action = self.menu_bar.addMenu("File").addAction("Exit")
            self._connect(self.exit_action.triggered, lambda *args: self.close())
            self.root.insertWidget(0, self.menu_bar)
        self.root.addWidget(self.view, 1)
        self.selection_status = QtGui.QLabel("Select an entry") if outline else None
        if self.selection_status is not None:
            self.root.addWidget(self.selection_status)
        self.status = QtGui.QLabel()
        self.status.setWordWrap(True)
        self.root.addWidget(self.status)
        buttons = QtGui.QHBoxLayout()
        buttons.addStretch(1)
        self.refresh_button, self.close_button = (
            QtGui.QPushButton("Refresh"),
            QtGui.QPushButton("Close"),
        )
        for button, slot in [
            (self.refresh_button, self.refresh),
            (self.close_button, self.close),
        ]:
            buttons.addWidget(button)
            self._connect(button.clicked, lambda *args, action=slot: action())
        self.root.addLayout(buttons)
        self._completion_lifetime.on_destroyed.append(self._dispose)
        if parent is not None:
            self._connect(parent.destroyed, lambda *args: self._dispose())
        self.resize(700, 650)
        self.refresh()

    def _detach(self) -> None:
        for signal, slot in self._selection_connections:
            try:
                signal.disconnect(slot)
            except Exception as error:  # noqa: BLE001 - contain native UI/virtual teardown failures
                self._disconnect_errors.append(str(error))
            self._connections.remove((signal, slot))
        self._selection_connections.clear()
        previous, self.model = self.model, None
        try:
            self.view.setModel(None)
        finally:
            if previous is not None:
                previous.deactivate()
        if self._selection is not None:
            self._selection.deleteLater()
            self._selection = None
        if previous is not None:
            previous.deleteLater()
        if self.selection_status is not None:
            self.selection_status.setText("Select an entry")

    def refresh(self) -> None:
        if self._closed:
            return
        try:
            self._detach()
            deadline = monotonic() + 2.0
            snapshot = self._capture(deadline=deadline)
            if self._closed:
                return
            if not isinstance(snapshot, Tree):
                raise TypeError("Capture must return a complete immutable Tree.")
            self.model = TreeModel(
                snapshot, self, outline=self.outline, deadline=deadline
            )
            check_deadline(deadline)
            self.view.setModel(self.model)
            self._selection = self.view.selectionModel()
            if self.outline:
                before = len(self._connections)
                current = self.model
                self._connect(
                    self._selection.currentChanged,
                    lambda index, old: self._selected(current, index),
                )
                self._selection_connections = self._connections[before:]
            self.view.setColumnWidth(0, 270)
            if self.model.error:
                raise ValueError(self.model.error)
            roots = sum(parent == -1 for parent, _ in snapshot.rows)
            self.status.setText(
                f"{roots} glyphs; {len(snapshot.rows)} complete rows. Refresh after font changes."
            )
        except Exception as error:  # noqa: BLE001 - contain native UI/virtual teardown failures
            if not self._closed:
                self._detach()
                self.status.setText(str(error))

    def _selected(self, model: Any, index: Any) -> None:
        if self._closed or model is not self.model:
            return
        self.selection_status.setText(
            f"Row {index.row() + 1}, column {index.column() + 1}"
            if index.isValid()
            else "No selection"
        )

    def _dispose(self) -> None:
        if self._closed:
            return
        self._closed, self._capture = True, None
        previous = self.model
        try:
            self._detach()
        except Exception as error:  # noqa: BLE001 - contain native UI/virtual teardown failures
            self.model, self._selection = None, None
            self._disconnect_errors.append(str(error))
        finally:
            if previous is not None:
                previous.deactivate()
        for signal, slot in reversed(self._connections):
            try:
                signal.disconnect(slot)
            except Exception as error:  # noqa: BLE001 - contain native UI/virtual teardown failures
                self._disconnect_errors.append(str(error))
        self._connections.clear()
        windows = getattr(sys, "_fontlab_samples", {})
        if windows.get(self.KEY) is self:
            windows.pop(self.KEY)

    def closeEvent(self, event: Any) -> None:
        self._dispose()
        super().closeEvent(event)
