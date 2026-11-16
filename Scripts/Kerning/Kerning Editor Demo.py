# this_file: Scripts/Kerning/Kerning Editor Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Open App's kerning editor on the current font, with no way to apply.

What: Opens a nonmodal editor built on App's kerning editor shell
(fontlabapp.kerning.edit.ui.KerningEditDialog). It lists the largest explicit
pairs of the chosen master. Double-click a value to type a new one; the shell
checks that both sides exist and parses the number, and the panel counts the
staged edits. A blank value stages a deletion.
Use: Open a font and run it. Choose a master, edit values, click Revert to
discard the staged edits or Refresh to read the font again, and Close when
done. At most 300 pairs, largest by size, are listed.
Safety: Nothing is applied. This editor has no Apply button and never calls
the batch writer: edits stay in the panel and are lost when you Revert,
Refresh or Close. Each refresh reads the explicit pairs and classes of every
master (the shell takes a snapshot before and after, plus the demo's own
read) and binds to that snapshot, without switching the active master. It
writes no font, master, selection, history, preference, Output or clipboard.
With no font open nothing opens.
"""

TITLE = "Kerning Editor Demo"
MAX_ROWS = 300
VALUE_COLUMN = 2


def dialog_class() -> type:
    """Build the editor class on the shared kerning editor shell, without Apply."""
    import fly
    from fly.ap.core.scripting import kerning_editor_refresh, kerning_pairs
    from fly.ap.kerning.edit.ui import KerningEditDialog

    gui = fly.qt.QtGui
    core = fly.qt.QtCore

    class PairEditor(KerningEditDialog):
        """Table of explicit pairs whose values can be staged but never applied."""

        KEY = "kerning_editor_demo"

        def __init__(self, parent=None) -> None:
            super().__init__(parent, TITLE, self.KEY)
            self.subtitle.setText("Double-click a value to stage a new one. Staged edits are never applied.")
            self.filling = False
            self.master_box = gui.QComboBox()
            self.master_box.addItems(self.masters)
            if self.current_master in self.masters:
                self.master_box.setCurrentIndex(self.masters.index(self.current_master))
            form = gui.QFormLayout()
            form.addRow("Master", self.master_box)
            self.root.addLayout(form)
            self.table = self.make_table(["Left", "Right", "Value"])
            self.table.setEditTriggers(gui.QAbstractItemView.DoubleClicked | gui.QAbstractItemView.EditKeyPressed)
            self.root.addWidget(self.table, 1)
            footer = gui.QHBoxLayout()
            self.status = gui.QLabel()
            self.status.setWordWrap(True)
            self.revert_button = gui.QPushButton("Revert")
            self.close_button = gui.QPushButton("Close")
            footer.addWidget(self.status, 1)
            footer.addWidget(self.revert_button)
            footer.addWidget(self.close_button)
            self.root.addLayout(footer)
            self.add_refresh(footer, lambda: self.refresh())
            self._connect(self.master_box.currentIndexChanged, lambda *args: self.refresh())
            self._connect(self.table.cellChanged, lambda row, column: self.cell_changed(row, column))
            self._connect(self.revert_button.clicked, lambda *args: self.refresh())
            self._connect(self.close_button.clicked, lambda *args: self.close())
            self.refresh()

        def master(self) -> str:
            """The master chosen in the combo box."""
            return self.masters[self.master_box.currentIndex]

        @kerning_editor_refresh
        def refresh(self) -> None:
            """Read the whole font, drop staged edits and fill the table."""
            self.filling = True
            try:
                self.staged, self.errors = {}, {}
                self.values = kerning_pairs(self.package, self.master())
                self.order = sorted(self.values, key=lambda pair: (-abs(self.values[pair]), pair))[:MAX_ROWS]
                self.table.setRowCount(len(self.order))
                for row, pair in enumerate(self.order):
                    for column, text in enumerate((pair[0], pair[1], f"{self.values[pair]:g}")):
                        item = gui.QTableWidgetItem(text)
                        if column != VALUE_COLUMN:
                            item.setFlags(int(item.flags()) & ~int(core.Qt.ItemIsEditable))
                        self.table.setItem(row, column, item)
            finally:
                self.filling = False
            self.revert_button.setEnabled(True)  # a failed refresh disables it; a good one restores it
            self.status.setText(f"{self.master()}: {len(self.values)} explicit pairs; {len(self.order)} shown. No edits staged.")

        def cell_changed(self, row: int, column: int) -> None:
            """Stage the edited value and report the count; nothing is written."""
            if self.filling or column != VALUE_COLUMN or row >= len(self.order):
                return
            pair = self.order[row]
            problem = self.stage_editor_cell(pair, self.master(), self.table.item(row, column).text(), self.values[pair])
            text = f"{len(self.staged)} edit(s) staged, none applied. Revert discards them."
            self.status.setText(f"{problem}. {text}" if problem else text)

    return PairEditor


def main() -> None:
    """Open the editor on the current font, or say that a font is needed."""
    import fly
    from fly.ap.core.scripting import current_package, show_script_dialog
    from fly.ap.qt.dialogs import run_standard_message_box

    qt = fly.qt
    parent = fly.fl.MainWindow()
    kind = qt.QtGui.QMessageBox
    if current_package() is None:
        run_standard_message_box(qt, parent, TITLE, "Open a font first. The editor lists its kerning.", "Information", kind.Ok)
        return
    try:
        panel = dialog_class()
        show_script_dialog(panel, panel.KEY)
    except (ValueError, RuntimeError, TimeoutError) as error:
        run_standard_message_box(qt, parent, TITLE, f"The editor did not open: {error}", "Warning", kind.Ok)


if __name__ == "__main__":
    main()
