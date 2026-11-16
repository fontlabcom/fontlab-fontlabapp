# this_file: src/fontlabapp/studios/kerning_studio/pairs.py
# SPDX-License-Identifier: Apache-2.0
"""Stage the original Pair Editor's complete multi-pair, multi-master batch."""
from typing import Any

from PythonQt import QtCore, QtGui

import fontlabapp.fontui as fontui
from fontlabapp.core import scripting
from fontlabapp.core.scripting import kerning_editor_api

from fontlabapp.studios._kerning_ui import Panel, button, combo, get, line_edit

model = kerning_editor_api()


def current_glyph_name(package: Any) -> str | None:
    names = scripting.names_selected_names() if package is not None else []
    return names[0] if names else None


def write_kerning(package: Any, edits: dict) -> None:
    model.write_kerning(package, edits, "Kerning Pair Editor")


class PairEditorPanel(Panel):
    """Editable master cells retain explicit zero, absence and side-specific classes."""

    ACTION = "Apply staged pairs"

    def __init__(self, tool: Any) -> None:
        super().__init__(tool)
        self.rows, self.staged, self.errors = {}, {}, {}
        self.snapshot = None
        self.history_stale = False
        self.draft_target = None
        self.table_masters: tuple[str, ...] = ()
        self.slot_error = ""
        self.glyph_field = line_edit(self.widget, placeholder="Glyph name")
        self.glyph_field.setText(current_glyph_name(tool.shell.package()) or "")
        self.layout.addWidget(self.glyph_field)
        self.table = QtGui.QTableWidget(self.widget)
        self.table.setAccessibleName("Kerning pairs and master values")
        self.table.horizontalHeader().setSortIndicator(0, QtCore.Qt.AscendingOrder)
        self.table.horizontalHeader().setSectionResizeMode(QtGui.QHeaderView.Interactive)
        self.layout.addWidget(self.table, 1)
        self.side = combo(self.widget, ["Glyph + partner", "Partner + glyph"])
        self.layout.addWidget(self.side)
        self.partner = line_edit(self.widget, placeholder="Partner glyph or @class")
        self.layout.addWidget(self.partner)
        self.add_button = button(self.widget, self.layout, "Add row", self.contain(self.add_row))
        self.partner.returnPressed.connect(self.contain(self.add_row))
        self.revert_button = button(self.widget, self.layout, "Revert staged pairs", self.revert)
        self.table.itemChanged.connect(self.contain(self.cell_edited))
        self.table.currentCellChanged.connect(self.contain(lambda row, *args: self.row_chosen(row)))
        tool.shell.set_actions(self.widget, refresh=self.reload_view, preview=self.accept_preview,
                               apply=self.apply, ready=self.ready, dirty=lambda: bool(self.staged or self.errors),
                               apply_label=self.ACTION)

    @property
    def glyph(self) -> str | None:
        return get(self.glyph_field.text).strip() or None

    @property
    def order(self) -> list:
        return list(self.rows)

    def clear(self) -> None:
        self.rows, self.staged, self.errors, self.snapshot = {}, {}, {}, None
        self.table.setRowCount(0)

    def failed(self, error: BaseException) -> None:
        if not (self.staged or self.errors or self.history_stale or
                get(self.table.state) == QtGui.QAbstractItemView.EditingState):
            self.clear()
        self.history_stale = True
        self.slot_error = str(error)
        self.tool.say(f"Error: {error} Use Refresh to scan again.")

    def refresh(self) -> None:
        if self.staged or self.errors or self.history_stale:
            self.tool.say("Staged pairs kept. Preview Changes to refresh their baseline, or Revert to discard.")
            return
        glyph = get(self.glyph_field.text).strip()
        self.snapshot = fontui.kerning_snapshot(self.tool.package) if self.tool.package is not None else None
        found = model.involving(self.tool.package, self.tool.masters, glyph) if self.snapshot and glyph else {}
        self.table_masters = tuple(self.tool.masters)
        self.draft_target = self.glyph, self.table_masters
        self.rows = dict(sorted(found.items()))
        self.fill()

    def revert(self) -> None:
        self.staged, self.errors = {}, {}
        self.history_stale = False
        self.refresh()

    def fill(self) -> None:
        self.table.blockSignals(True)
        self.table.setSortingEnabled(False)
        self.table.setColumnCount(len(self.table_masters) + 1)
        self.table.setHorizontalHeaderLabels(["Pair", *self.table_masters])
        self.table.setRowCount(len(self.rows))
        for row, pair in enumerate(self.rows):
            item = QtGui.QTableWidgetItem("  ".join(pair))
            item.setData(QtCore.Qt.UserRole, pair)
            item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
            self.table.setItem(row, 0, item)
            for column, master in enumerate(self.table_masters, 1):
                key = pair, master
                value = self.staged.get(key, self.rows[pair].get(master))
                item = QtGui.QTableWidgetItem(self.errors.get(key, "" if value is None else f"{value:g}"))
                if key not in self.errors and value is not None:
                    item.setData(QtCore.Qt.DisplayRole, value)
                font = item.font()
                font.setBold(key in self.staged)
                item.setFont(font)
                self.table.setItem(row, column, item)
        self.table.setSortingEnabled(True)
        self.table.blockSignals(False)
        self.preview()

    def cell_edited(self, item: Any) -> None:
        if item.column() == 0:
            self.table.blockSignals(True)
            item.setText("  ".join(item.data(QtCore.Qt.UserRole)))
            self.table.blockSignals(False)
            return
        pair = tuple(self.table.item(item.row(), 0).data(QtCore.Qt.UserRole))
        master = self.table_masters[item.column() - 1]
        text = get(item.text)
        try:
            package = self.draft_package()
            if not self.history_stale and fontui.kerning_snapshot(package) != self.snapshot:
                raise ValueError("Kerning results are stale; use Refresh.")
        except (ValueError, RuntimeError, TypeError, AttributeError) as error:
            self.history_stale = True
            self.slot_error = str(error)
            self.tool.say(f"Error: {error}")
            return
        try:
            self.tool.backends().batch.validate_pair(package, master, pair)
        except ValueError as error:
            self.staged.pop((pair, master), None)
            self.errors[(pair, master)] = text
            self.tool.say(str(error))
            return
        valid = model.stage_cell(self.staged, self.errors, (pair, master), text, self.rows[pair].get(master))
        self.table.blockSignals(True)
        if (pair, master) not in self.errors:
            value = self.staged.get((pair, master), self.rows[pair].get(master))
            item.setData(QtCore.Qt.DisplayRole, "" if value is None else value)
        font = item.font()
        font.setBold((pair, master) in self.staged)
        item.setFont(font)
        self.table.blockSignals(False)
        self.preview()
        if not valid:
            self.tool.say(f"“{text}” is not a valid kerning value; other valid edits remain staged")

    def set_cell(self, left: str, right: str, master: str, text: str) -> None:
        for row in range(get(self.table.rowCount)):
            if tuple(self.table.item(row, 0).data(QtCore.Qt.UserRole)) == (left, right):
                self.table.item(row, self.table_masters.index(master) + 1).setText(text)
                return
        raise ValueError("Add the pair row first.")

    def add_row(self) -> None:
        if self.history_stale:
            self.tool.say("Preview Changes before adding rows; existing drafts are kept.")
            return
        glyph, partner = get(self.glyph_field.text).strip(), get(self.partner.text).strip()
        if not glyph or not partner or self.snapshot is None:
            return
        pair = (glyph, partner) if get(self.side.currentIndex) == 0 else (partner, glyph)
        if not model.partner_exists(self.tool.package, self.tool.masters, pair):
            self.tool.say(f"No glyph or side-compatible class named “{partner}”")
            return
        self.rows.setdefault(pair, {})
        self.fill()
        self.partner.setText("")

    def preview(self) -> None:
        glyph = self.glyph
        self.side.setItemText(0, f"{glyph or '…'}  +  partner")
        self.side.setItemText(1, f"partner  +  {glyph or '…'}")
        if self.tool.package is None:
            text = "Open a font first."
        elif glyph is None:
            text = "Select a glyph in the Font window, then run this script again."
        else:
            left, right = model.class_sides(self.tool.package, self.tool.masters[0], glyph)
            classes = ", ".join(c for c in (left, right) if c) or "no kerning class"
            text = f"Pairs with {glyph} ({classes}) on either side. Empty cell = no pair; clear a cell to delete that pair."
        self.subtitle.setText(text)
        count = len(self.staged)
        self.tool.say(f"{count} edited cell{'s' if count != 1 else ''}" if count else f"{len(self.rows)} pairs")
        self.revert_button.setEnabled(bool(self.staged or self.errors))

    def invalidate_history(self) -> None:
        """Keep table/editor text untouched while invalidating its accepted baseline."""
        self.history_stale = self.history_stale or bool(self.staged or self.errors) or get(self.table.state) == QtGui.QAbstractItemView.EditingState

    def draft_package(self) -> Any:
        """Validate the captured font and displayed master columns before touching drafts."""
        package = self.tool.shell.package()
        if package is None or self.draft_target != (self.glyph, tuple(package.masters)):
            raise ValueError("The captured glyph or master layout changed; reopen this tool.")
        return package

    def accept_preview(self) -> None:
        """Explicitly rebase preserved drafts on fresh same-target cells, with or without hooks."""
        self.history_stale = True
        package = self.draft_package()
        snapshot = fontui.kerning_snapshot(package)
        if get(self.table.state) == QtGui.QAbstractItemView.EditingState:
            editor = self.table.findChild(QtGui.QLineEdit)
            if editor is None:
                raise ValueError("Finish editing the active cell, then Preview Changes again.")
            self.table.commitData(editor)
            self.table.closeEditor(editor, QtGui.QAbstractItemDelegate.NoHint)
        staged, errors = dict(self.staged), dict(self.errors)
        for row in range(get(self.table.rowCount)):
            pair = tuple(self.table.item(row, 0).data(QtCore.Qt.UserRole))
            for column, master in enumerate(self.table_masters, 1):
                model.stage_cell(staged, errors, (pair, master), get(self.table.item(row, column).text),
                                 self.rows[pair].get(master))
        if errors:
            raise ValueError("Correct invalid cells before accepting the preview.")
        for pair, master in staged:
            self.tool.backends().batch.validate_pair(package, master, pair)
        rows = model.involving(package, list(self.table_masters), self.glyph)
        kept = {pair for pair, _master in staged} | {pair for pair, values in self.rows.items() if not values}
        for pair in kept:
            rows.setdefault(pair, {})
        if fontui.kerning_snapshot(package) != snapshot:
            raise ValueError("Kerning changed during preview; Preview Changes again.")
        self.rows, self.staged, self.errors = dict(sorted(rows.items())), staged, errors
        self.tool.package, self.snapshot, self.history_stale = package, snapshot, False
        self.fill()
        self.tool.shell._update_actions()

    def ready(self) -> bool:
        return bool(self.staged) and self.snapshot is not None and not self.history_stale

    def apply(self) -> bool:
        if not self.ready():
            return False
        edits = {}
        for (pair, master), value in self.staged.items():
            edits.setdefault(master, {})[pair] = value
        done = bool(self.run(lambda: self.tool.write("Edit pairs", "staged cells", edits, self.snapshot)))
        if done:
            count = len(self.staged)
            try:
                self.revert()
                if self.tool.preview is not None:
                    self.tool.preview.refresh()
            except (ValueError, RuntimeError, AttributeError, TypeError) as error:
                self.clear()
                self.tool.say(f"Kerning was applied; preview failed: {error}. Use Edit > Undo or Refresh.")
                return False
            self.tool.say(f"Wrote {count} cells in {len(edits)} masters")
        else:
            self.history_stale = True
        return done

    def row_chosen(self, row: int) -> None:
        if row >= 0:
            pair = tuple(self.table.item(row, 0).data(QtCore.Qt.UserRole))
            self.tool.show_pair(*pair, self.tool.current)
