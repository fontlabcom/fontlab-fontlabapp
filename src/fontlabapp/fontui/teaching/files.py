# this_file: src/fontlabapp/fontui/teaching/files.py
# SPDX-License-Identifier: Apache-2.0
"""File Search and Image Viewer labs retain both original teaching profiles."""
from typing import Any

from PythonQt import QtCore, QtGui

from fontlabapp.qt.find_files import actions
from fontlabapp.qt.find_files.ui import dialog_type
from fontlabapp.qt.images.viewer.ui import panel_type
from fontlabapp.qt.properties import value
from . import host


class SizeItem(QtGui.QTableWidgetItem):
    """Sort displayed KiB numerically without changing the stored file path."""

    def __lt__(self, other: Any) -> bool:
        return self.data(QtCore.Qt.UserRole + 1) < other.data(QtCore.Qt.UserRole + 1)


def search_panel(profile: str, parent: Any) -> Any:
    """Add stable sorting identities around the unchanged incremental search."""
    base = dialog_type(profile)

    class SearchPanel(base):
        def tick(self) -> None:
            start = len(self._paths)
            self.table.setSortingEnabled(False)
            try:
                super().tick()
                for row in range(start, len(self._paths)):
                    self.table.item(row, 0).setData(QtCore.Qt.UserRole, str(self._paths[row]))
                    old = self.table.item(row, 1)
                    item = SizeItem(str(value(old, "text")))
                    item.setFlags(old.flags())
                    item.setData(QtCore.Qt.UserRole + 1, self._search.results[row].size)
                    self.table.setItem(row, 1, item)
            finally:
                self.table.setSortingEnabled(True)

        def _action(self, callback: Any, *args: Any) -> None:
            if callback is actions.activate and not self._closed:
                row = args[0]
                item = self.table.item(row, 0)
                if item is not None:
                    path = item.data(QtCore.Qt.UserRole)
                    try:
                        if not self._gui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(path)):
                            self.status.setText("Could not open the selected file.")
                    except Exception as error:  # Qt callbacks must retain the error in this panel.
                        self.status.setText(str(error))
                return
            super()._action(callback, *args)

    panel = SearchPanel(parent)
    panel.table.horizontalHeader().setSectionResizeMode(QtGui.QHeaderView.Interactive)
    panel.table.horizontalHeader().setStretchLastSection(True)
    return panel


def show_search(parent: Any = None) -> Any:
    """Open both complete file search profiles in one owned teaching shell."""
    shell = host.create("File Search Lab", parent=parent)
    try:
        for title, profile in (("Text search", "text"), ("Bytes profile", "bytes")):
            panel = search_panel(profile, shell.tabs)
            owner = host.embed(shell, title, panel)
            shell.set_actions(owner, refresh=lambda p=panel: p._action(actions.begin))
        return host.finish(shell)
    except BaseException:
        shell.close()
        raise


def show_images(parent: Any = None) -> Any:
    """Keep free and bounded zoom, Fit and print behavior independently selectable."""
    shell = host.create("Image Viewer Lab", parent=parent)
    try:
        for title, part in (("Full viewer", 2), ("Bounded zoom", 3)):
            panel = panel_type(QtCore, QtGui, part)(shell.tabs)
            panel.commands["exit"].setVisible(False)
            panel.commands["exit"].setEnabled(False)
            host.embed(shell, title, panel)
        return host.finish(shell)
    except BaseException:
        shell.close()
        raise
