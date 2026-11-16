# this_file: src/fontlabapp/guides/rewrite/editor_ui.py
# SPDX-License-Identifier: Apache-2.0
"""Original editable guide rows with guarded Add/Delete and complete parsing."""

from fontlabapp.guides.rewrite.ui import RewriteDialog
from fontlabapp.guides.inspect.ui import QtCore, QtGui, api
from fontlabapp.guides.records import parse_row
from fontlabapp.core.scripting import components_action


class GuideListDialog(RewriteDialog):
    """Keep row operations within the complete captured glyph/master context."""

    def layers(self) -> list:
        """Check binding before any cached native glyph lookup."""
        self.check_binding()
        return (
            api.master_layers(self.glyph, self.chosen_masters())
            if self.glyph is not None
            else []
        )

    def editable_masters(self) -> list[str]:
        """Keep automatic layers read-only, matching the original editor."""
        return [master for master, layer in self.layers() if not layer.autoLayer]

    def set_row(self, row: int, master: str, values: tuple) -> None:
        """Retain original units, alignment and read-only master labels."""
        ink = QtGui.QColor(self.palette.color(QtGui.QPalette.WindowText))
        x, y, angle, name = values
        for column, text in enumerate([master, f"{x:g}", f"{y:g}", f"{angle:g}", name]):
            item = QtGui.QTableWidgetItem(text)
            item.setForeground(QtGui.QBrush(ink))
            if column == 0:
                item.setFlags(int(item.flags()) & ~int(QtCore.Qt.ItemIsEditable))
            elif column < 4:
                item.setTextAlignment(
                    int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                )
            self.table.setItem(row, column, item)

    @components_action
    def add_row(self) -> None:
        """Add an original default guide to one explicitly editable master."""
        masters = self.editable_masters()
        if not masters:
            return
        master = self.current_master if self.current_master in masters else masters[0]
        row = self.table.rowCount
        self.table.setRowCount(row + 1)
        self.set_row(row, master, (0.0, 0.0, 0.0, "new guide"))
        self.table.setCurrentCell(row, 2)

    @components_action
    def delete_row(self) -> None:
        """Delete the selected proposal row; native guides change only on Apply."""
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)

    def table_records(self) -> dict[str, list]:
        """Parse every cell before writing; refuse any unknown master label."""
        records = {master: [] for master in self.editable_masters()}
        for row in range(self.table.rowCount):
            cells = []
            for column in range(5):
                item = self.table.item(row, column)
                cells.append(item.text() if item is not None else "")
            master, values = parse_row(cells, row)
            if master not in records:
                raise ValueError(f"row {row + 1}: master changed; reopen this tool")
            records[master].append(values)
        return records
