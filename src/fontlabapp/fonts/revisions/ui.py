# this_file: src/fontlabapp/fonts/revisions/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Explicit, read-only comparison of two registered open font revisions."""

import json
import sys
from dataclasses import asdict, is_dataclass
from functools import wraps
from importlib import import_module
from pathlib import Path
from typing import Any

from fontlabapp import _native
from fontlabapp.glyphs.names.ui import NamesDialog, QtCore, QtGui

api = import_module("fontlabapp.fonts.revisions.model")

FIELD_LABELS = {
    "master_presence": "Master presence",
    "glyph_order": "Glyph order",
    "glyph_presence": "Glyph presence",
    "state": "Layer state",
    "advance": "Advance width",
    "geometry": "Contour/node geometry",
    "anchors": "Anchors",
    "components": "Components",
    "raw_node_state": "Raw node flags (includes selection)",
}


def _contained(method: Any) -> Any:
    """Contain failures even during construction or direct action invocation."""

    @wraps(method)
    def action(self: Any, *args: Any) -> None:
        if self._closed or self._loading:
            return
        try:
            method(self, *args)
        except Exception as error:  # noqa: BLE001 - contain native UI callbacks
            self.invalidate()
            self.slot_error = repr(error)
            self.status.setText("Error: " + str(error))

    return action


class RevisionCompareDialog(NamesDialog):
    """Keep two explicit source identities; never activate a font or master."""

    TITLE = "Compare Open Font Revisions"
    KEY = "compare_open_font_revisions"

    def __init__(self, parent: Any = None) -> None:
        NamesDialog.__init__(self, parent, self.TITLE, self.KEY)
        self._closed, self._loading = False, False
        self._disconnect_errors = []
        self.choices, self.rows, self.shown, self.snapshots = (), (), (), ()
        self._result_selection = None
        self._masters = {"left": (), "right": ()}
        self.setModal(False)
        self.resize(1040, 720)
        self.subtitle.setText(
            "Compare glyph presence, advance widths, raw contour/node geometry, "
            "anchors and components in two explicitly chosen masters. "
            "Raw node flags include selection and are reported separately. "
            "This is a read-only field comparison, not complete semantic font equality."
        )
        grid = QtGui.QGridLayout()
        for row, side in enumerate(("left", "right")):
            font_box, master_box = QtGui.QComboBox(), QtGui.QComboBox()
            setattr(self, side + "_font", font_box)
            setattr(self, side + "_master", master_box)
            grid.addWidget(QtGui.QLabel(side.title() + " font"), row, 0)
            grid.addWidget(font_box, row, 1)
            grid.addWidget(QtGui.QLabel("Master"), row, 2)
            grid.addWidget(master_box, row, 3)
        self.root.addLayout(grid)
        controls = QtGui.QHBoxLayout()
        self.refresh_button = QtGui.QPushButton("Refresh Font List")
        self.compare_button = QtGui.QPushButton("Compare")
        self.search = QtGui.QLineEdit()
        self.search.setPlaceholderText("Search glyph or changed field")
        for widget in (self.refresh_button, self.compare_button, self.search):
            controls.addWidget(widget)
        self.root.addLayout(controls)
        self.table = self.make_table(["Glyph", "Changed Fields"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.root.addWidget(self.table, 1)
        self.root.addWidget(QtGui.QLabel("Named-field details (left / right)"))
        self.details = QtGui.QPlainTextEdit()
        self.details.setReadOnly(True)
        self.root.addWidget(self.details, 1)
        footer = QtGui.QHBoxLayout()
        self.status = QtGui.QLabel()
        self.status.setWordWrap(True)
        self.close_button = QtGui.QPushButton("Close")
        footer.addWidget(self.status, 1)
        footer.addWidget(self.close_button)
        self.root.addLayout(footer)
        for side in ("left", "right"):
            self._connect(
                getattr(self, side + "_font").currentIndexChanged,
                lambda *args, side=side: self.font_changed(side),
            )
            self._connect(
                getattr(self, side + "_master").currentIndexChanged,
                lambda *args: self.choices_changed(),
            )
        self._connect(self.refresh_button.clicked, lambda *args: self.refresh_fonts())
        self._connect(self.compare_button.clicked, lambda *args: self.compare_fonts())
        self._connect(self.search.textChanged, lambda *args: self.filter_rows())
        self._connect(
            self.table.itemSelectionChanged, lambda *args: self.show_details()
        )
        self._connect(self.close_button.clicked, lambda *args: self.close())
        self._completion_lifetime.on_destroyed.append(self._destroyed)
        if parent is not None:
            self._connect(parent.destroyed, lambda *args: self._destroyed())
        self.refresh_fonts()

    def _connect(self, signal: Any, slot: Any) -> None:
        """Contain every retained callback, including Close, after destruction."""

        def live(*args: Any) -> None:
            if not self._closed:
                slot(*args)

        super()._connect(signal, live)

    def _destroyed(self) -> None:
        """Disconnect owned slots while parent/direct destruction leaves children alive."""
        self._closed = True
        # Qt5 QWidget emits destroyed before deleteChildren (qwidget.cpp:1379/1402).
        # Release PythonQt receivers while these owned child emitters still exist.
        for signal, slot in reversed(tuple(self._connections)):
            try:
                signal.disconnect(slot)
            except Exception as error:  # noqa: BLE001 - never escape a native destructor
                self._disconnect_errors.append(repr(error))
        self._connections.clear()
        self.rows, self.shown, self.snapshots = (), (), ()
        self._result_selection, self._snapshot_valid = None, False
        windows = getattr(sys, "_fontlab_samples", {})
        if windows.get(self.KEY) is self:
            windows.pop(self.KEY)

    @staticmethod
    def _workspace() -> Any:
        return _native("fontlab").flWorkspace.instance()

    def _selection(self) -> tuple:
        selections = []
        for side in ("left", "right"):
            index = getattr(self, side + "_font").currentIndex
            master = getattr(self, side + "_master").currentIndex
            selections.append(
                (
                    self.choices[index].font_id if index >= 0 else None,
                    self._masters[side][master] if master >= 0 else None,
                )
            )
        return tuple(selections)

    def _set_masters(self, side: str, previous: str | None = None) -> None:
        index = getattr(self, side + "_font").currentIndex
        names = self.choices[index].masters if index >= 0 else ()
        missing = previous is not None and index >= 0 and previous not in names
        self._masters[side] = names + ((previous,) if missing else ())
        box = getattr(self, side + "_master")
        box.clear()
        box.addItems(list(names) + ([previous + " (missing)"] if missing else []))
        box.setCurrentIndex(
            self._masters[side].index(previous)
            if previous in self._masters[side]
            else (0 if names else -1)
        )

    @_contained
    def refresh_fonts(self) -> None:
        """Explicit refresh preserves IDs and named masters, including missing ones."""
        selected = self._selection()
        self.invalidate()
        choices = api.font_choices(self._workspace())
        self._loading = True
        try:
            self.choices = choices
            ids = [choice.font_id for choice in choices]
            labels = [
                f"{i + 1} · {Path(c.path).name if c.path else 'Unsaved font'} — {c.label}"
                for i, c in enumerate(choices)
            ]
            for side, (identifier, master) in zip(("left", "right"), selected):
                box = getattr(self, side + "_font")
                box.clear()
                box.addItems(labels)
                for index, choice in enumerate(choices):
                    box.setItemData(
                        index, choice.path or "Unsaved font", QtCore.Qt.ToolTipRole
                    )
                box.setCurrentIndex(ids.index(identifier) if identifier in ids else -1)
                self._set_masters(side, master)
        finally:
            self._loading = False
        message = "Choose two different fonts and their masters, then Compare."
        if not choices:
            message = "No open fonts. Open two fonts, then Refresh Font List."
        elif len(choices) == 1:
            message = "This tool needs two open fonts; then Refresh Font List."
        self.status.setText(message)

    @_contained
    def font_changed(self, side: str) -> None:
        self._loading = True
        try:
            self._set_masters(side)
        finally:
            self._loading = False
        self.choices_changed()

    @_contained
    def choices_changed(self) -> None:
        self.invalidate()
        self.status.setText(
            "Choices changed; choose both fonts and masters, then Compare."
        )

    def _check_domain(self, workspace: Any) -> None:
        if api.font_choices(workspace) != self.choices:
            raise ValueError("Open font registration changed; use Refresh Font List.")

    @_contained
    def compare_fonts(self) -> None:
        self.invalidate()
        selection = self._selection()
        if any(
            identifier is None or master is None for identifier, master in selection
        ):
            raise ValueError("Choose both fonts and their masters.")
        if selection[0][0] == selection[1][0]:
            raise ValueError("Choose two different open fonts.")
        workspace = self._workspace()
        self._check_domain(workspace)
        snapshots = tuple(
            api.capture(workspace, identifier, master)
            for identifier, master in selection
        )
        rows = api.compare(*snapshots)
        for snapshot in snapshots:
            api.validate(workspace, snapshot)
        self._check_domain(workspace)
        if selection != self._selection():
            raise ValueError("Choices changed during comparison; Compare again.")
        self.snapshots, self.rows = snapshots, rows
        self._result_selection, self._snapshot_valid = selection, True
        self.filter_rows()

    def ensure_snapshot(self) -> None:
        if self._closed:
            raise ValueError("Revision panel is closed.")
        if not self._snapshot_valid or self._selection() != self._result_selection:
            raise ValueError("Results are stale; Compare again.")
        workspace = self._workspace()
        self._check_domain(workspace)
        for snapshot in self.snapshots:
            api.validate(workspace, snapshot)

    @_contained
    def filter_rows(self) -> None:
        if not self.snapshots:
            return
        self.ensure_snapshot()
        search = self.search.text
        query = search.strip().casefold()
        shown = tuple(
            row for row in self.rows if query in self._row_text(row).casefold()
        )
        self._loading = True
        try:
            self.table.setRowCount(0)
            self.details.clear()
            self.table.setRowCount(len(shown))
            for index, row in enumerate(shown):
                for column, value in enumerate(
                    (
                        row.glyph or "(Font)",
                        ", ".join(FIELD_LABELS[f] for f in row.fields),
                    )
                ):
                    item = QtGui.QTableWidgetItem(value)
                    item.setToolTip(value)
                    self.table.setItem(index, column, item)
            self.ensure_snapshot()
            if self.search.text != search:
                raise ValueError("Search changed during filtering; Compare again.")
            self.shown = shown
        finally:
            self._loading = False
        self.status.setText(
            f"{len(self.rows)} differences; {len(shown)} shown. Sources verified; no changes made."
        )

    @staticmethod
    def _row_text(row: Any) -> str:
        return " ".join(
            (row.glyph, *row.fields, *(FIELD_LABELS[f] for f in row.fields))
        )

    @_contained
    def show_details(self) -> None:
        if not self.snapshots:
            return
        self.ensure_snapshot()
        index = self.table.currentRow()
        if index < 0:
            self.details.clear()
            return
        row = self.shown[index]
        lines = ["Glyph: " + (row.glyph or "(Font)")]
        for field in row.fields:
            lines.append(FIELD_LABELS[field])
            for side, record in (("Left", row.left), ("Right", row.right)):
                value = record
                if field not in ("glyph_presence", "glyph_order", "master_presence"):
                    value = getattr(
                        record,
                        "raw_node_states" if field == "raw_node_state" else field,
                    )
                if is_dataclass(value):
                    value = asdict(value)
                lines.append(
                    side + ": " + json.dumps(value, ensure_ascii=False, indent=2)
                )
        self.ensure_snapshot()
        self.details.setPlainText("\n".join(lines))

    def invalidate(self) -> None:
        """Clear every partial row without changing either explicit source choice."""
        if self._closed:
            return
        self._snapshot_valid = False
        self.rows, self.shown, self.snapshots = (), (), ()
        self._result_selection = None
        for name in ("table", "details"):
            widget = getattr(self, name, None)
            if widget is not None:
                widget.setRowCount(0) if name == "table" else widget.clear()

    def closeEvent(self, event: Any) -> None:
        if self._closed:
            event.accept()
            return
        self.invalidate()
        self._closed = True
        NamesDialog.closeEvent(self, event)
