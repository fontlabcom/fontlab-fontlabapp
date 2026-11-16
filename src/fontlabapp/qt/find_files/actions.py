# this_file: src/fontlabapp/qt/find_files/actions.py
# SPDX-License-Identifier: Apache-2.0
"""Owned actions for the two original Find Files profiles."""

from pathlib import Path
from typing import Any

from fontlabapp.qt.find_files.search import Search
from fontlabapp.qt.find_files.text import query, remember


def cancel(w: Any) -> None:
    """Stop only this query and release its directory and stream."""
    w._timer.stop()
    if w._search is not None:
        w._search.cancel()
    w.progress.hide()


def begin(w: Any) -> None:
    """Capture a query, clear prior rows and start bounded timer turns."""
    cancel(w)
    w.table.setRowCount(0)
    w._paths.clear()
    w._history_added = False
    w._query = tuple(
        query(w._qt, c) for c in (w.pattern, w.containing, w.directory)
    )
    pattern, needle, directory = w._query
    w._search = Search(Path(directory), pattern, needle, w._profile)
    w.status.setText("Searching…")
    w.progress.reset()
    w.progress.setRange(0, 0)
    if w._search.active:
        w.progress.show()
        w._timer.start(0)
    else:
        w.status.setText(w._search.error)


def tick(w: Any) -> None:
    """Read one chunk or scan one bounded set of entries, then publish results."""
    if w._closed or w._search is None:
        return
    search = w._search
    search.step(query(w._qt, w.pattern))
    if w._closed or w._search is not search:
        return
    if search.history_ready and not w._history_added:
        w._history_added = True
        for combo, text in zip((w.pattern, w.containing, w.directory), w._query):
            remember(w._qt, combo, text)
        w.progress.setRange(0, search.total)
    if w._profile == "bytes" and search.history_ready:
        w.progress.setValue(search.processed)
    for item in search.results[len(w._paths) :]:
        row = len(w._paths)
        w._paths.append(item.path)
        w.table.insertRow(row)
        size = (
            str(item.size_kib)
            if w._profile == "text"
            else f"{int((item.size + 1023) / 1024)} KB"
        )
        for column, text in enumerate((item.path.name, size)):
            cell = w._gui.QTableWidgetItem(text)
            if w._profile == "bytes":
                cell.setFlags(cell.flags() & ~w._core.Qt.ItemIsEditable)
                if column:
                    cell.setTextAlignment(
                        w._core.Qt.AlignRight | w._core.Qt.AlignVCenter
                    )
            w.table.setItem(row, column, cell)
    if not search.active:
        w._timer.stop()
        w.progress.hide()
        w.status.setText(search.error or f"{len(w._paths)} file(s) found")


def browse(w: Any) -> None:
    """Show an owned non-native directory chooser without a nested event loop."""
    if w._browser is None:
        from fontlabapp.core.scripting import connect_guarded

        browser = w._gui.QFileDialog(w)
        w._browser = browser
        browser.setOption(w._gui.QFileDialog.DontUseNativeDialog, True)
        browser.setFileMode(w._gui.QFileDialog.Directory)
        browser.setWindowModality(w._core.Qt.NonModal)

        def accepted(*args: Any) -> None:
            paths = browser.selectedFiles()
            if paths and not w._closed:
                w.directory.setEditText(str(paths[0]))

        connect_guarded(w, browser.accepted, accepted)
    directory = (
        w._initial_directory
        if w._profile == "text"
        else query(w._qt, w.directory)
    )
    w._browser.setDirectory(directory)
    w._browser.setWindowFlags(
        w._browser.windowFlags() | w._core.Qt.WindowStaysOnTopHint
    )
    w._browser.show()


def activate(w: Any, row: int) -> None:
    """Open the stored result path, independent of an edited table label."""
    if 0 <= row < len(w._paths):
        url = w._core.QUrl.fromLocalFile(str(w._paths[row]))
        if not w._gui.QDesktopServices.openUrl(url):
            w.status.setText("Could not open the selected file.")
