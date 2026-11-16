# this_file: src/fontlabapp/studios/anchor_transfer/csv_import.py
# SPDX-License-Identifier: Apache-2.0
"""CSV import tab: Add Anchors From File as a dry run, then one Undo step.

Reads a UTF-8 CSV (path field, Browse… and Load, as the original; the
original's columns, BOM and newline handling and its errors are unchanged
in ``transfer.load_table``), lists the anchor edits on the current master
and imports exactly those. Coordinates round half up to font units.
Apply writes one ``Anchor Transfer: import anchors <subject>`` Undo step.
"""

from typing import Any

from PythonQt import QtGui

from .._kerning_ui import button, get, label, line_edit, row
from . import transfer
from ._panel import AnchorPanel


class CsvPanel(AnchorPanel):
    """Add Anchors From File."""

    ACTION = "Import"
    UNDO = "import anchors"

    def build_controls(self, form: Any) -> None:
        self.csv_path = row(self.widget, form, "UTF-8 CSV path", line_edit(self.widget, "", ""))
        self.csv_path.returnPressed.connect(lambda *args: self.tool.reload())
        line = QtGui.QHBoxLayout()
        form.addLayout(line)
        button(self.widget, line, "Browse…", lambda: self.run(self.choose_csv))
        button(self.widget, line, "Load", self.tool.reload)
        self.csv_info = label(self.widget, form, transfer.CSV_INFO)
        self.records: dict = {}

    def choose_csv(self) -> None:
        """Choose a CSV in a file dialog, then load its preview."""
        path = QtGui.QFileDialog.getOpenFileName(self.widget, transfer.CSV_TITLE, "", transfer.CSV_FILTER)
        path = path[0] if isinstance(path, tuple) else path
        if path:
            self.csv_path.setText(str(path))
            self.tool.reload()

    def path(self) -> str:
        return str(get(self.csv_path.text)).strip()

    def target_glyphs(self) -> list[Any]:
        if not self.path():
            return []
        self.records, report = transfer.load_table(self.path())
        self.csv_info.setText(report)
        return transfer.csv_glyphs(self.tool.package, self.records)

    def empty_message(self) -> str:
        return "Choose an anchor CSV file, then press Load."

    def masters(self) -> list[str]:
        return [self.tool.current]

    def planner(self, glyphs: list[Any], masters: list[str]) -> Any:
        return transfer.csv_planner(self.records, glyphs, self.tool.current)


__all__ = ["CsvPanel"]
