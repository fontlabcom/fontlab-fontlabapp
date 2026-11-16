# this_file: Scripts/Kerning/Kerning Inspect Demo.py
# SPDX-License-Identifier: Apache-2.0
"""Browse the explicit kerning pairs of any master in a read-only panel.

What: Opens a nonmodal panel built on App's read-only kerning panel shell
(fontlabapp.kerning.inspect.ui.KerningDialog) that lists the largest explicit
pairs of the chosen master, class pairs written as @name, and counts the
pairs and classes. The master list holds every master of the open font.
Use: Open a font and run it. Choose a master, click Refresh after the font
changes and Close when done. At most 300 pairs, largest by size, are listed.
Safety: Read-only. The panel reads the explicit pairs and classes of the
chosen master without switching the active master. It has no Apply or edit
control and writes no font, master, selection, history, preference, Output or
clipboard. After a failed read it clears its table instead of showing a
partial list. With no font open nothing opens.
"""

TITLE = "Kerning Inspect Demo"
MAX_ROWS = 300


def dialog_class() -> type:
    """Build the inspector class on the shared read-only kerning shell."""
    import fly
    from fly.ap.core.scripting import kerning_classes, kerning_pairs, kerning_snapshot_refresh
    from fly.ap.kerning.inspect.ui import KerningDialog

    gui = fly.qt.QtGui

    class PairInspector(KerningDialog):
        """Table of the largest explicit pairs of one master."""

        KEY = "kerning_inspect_demo"

        def __init__(self, parent=None) -> None:
            super().__init__(parent, TITLE, self.KEY)
            self.subtitle.setText("Explicit pairs of one master, largest first. Read-only: nothing here changes the font.")
            self.master_box = gui.QComboBox()
            self.master_box.addItems(self.masters)
            if self.current_master in self.masters:
                self.master_box.setCurrentIndex(self.masters.index(self.current_master))
            form = gui.QFormLayout()
            form.addRow("Master", self.master_box)
            self.root.addLayout(form)
            self.table = self.make_table(["Left", "Right", "Value"])
            self.root.addWidget(self.table, 1)
            footer = gui.QHBoxLayout()
            self.status = gui.QLabel()
            self.status.setWordWrap(True)
            self.refresh_button = gui.QPushButton("Refresh")
            self.close_button = gui.QPushButton("Close")
            footer.addWidget(self.status, 1)
            footer.addWidget(self.refresh_button)
            footer.addWidget(self.close_button)
            self.root.addLayout(footer)
            self._connect(self.master_box.currentIndexChanged, lambda *args: self.refresh())
            self._connect(self.refresh_button.clicked, lambda *args: self.refresh())
            self._connect(self.close_button.clicked, lambda *args: self.close())
            self.refresh()

        @kerning_snapshot_refresh
        def scan(self) -> None:
            """Read one master completely, then fill the table."""
            master = self.masters[self.master_box.currentIndex]
            pairs = kerning_pairs(self.package, master)
            classes = kerning_classes(self.package, master)
            shown = sorted(pairs.items(), key=lambda item: (-abs(item[1]), item[0]))[:MAX_ROWS]
            self.table.setRowCount(len(shown))
            for row, ((left, right), value) in enumerate(shown):
                for column, text in enumerate((left, right, f"{value:g}")):
                    self.table.setItem(row, column, gui.QTableWidgetItem(text))
            self.status.setText(f"{master}: {len(pairs)} explicit pairs, {len(classes)} classes; {len(shown)} shown. Nothing changed.")

        def refresh(self) -> None:
            """Scan again; show a failed read in the status line."""
            try:
                self.scan()
            except (ValueError, RuntimeError) as error:
                self.status.setText(f"Error: {error}")

    return PairInspector


def main() -> None:
    """Open the inspector on the current font, or say that a font is needed."""
    import fly
    from fly.ap.core.scripting import current_package, show_script_dialog
    from fly.ap.qt.dialogs import run_standard_message_box

    qt = fly.qt
    parent = fly.fl.MainWindow()
    kind = qt.QtGui.QMessageBox
    if current_package() is None:
        run_standard_message_box(qt, parent, TITLE, "Open a font first. The panel lists its kerning.", "Information", kind.Ok)
        return
    try:
        panel = dialog_class()
        show_script_dialog(panel, panel.KEY)
    except (ValueError, RuntimeError, TimeoutError) as error:
        run_standard_message_box(qt, parent, TITLE, f"The panel did not open: {error}", "Warning", kind.Ok)


if __name__ == "__main__":
    main()
