# this_file: src/fontlabapp/qt/find_files/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Nonmodal, explicitly owned Find Files windows for PythonQt."""

from pathlib import Path
from typing import Any

from fontlabapp.qt.find_files import actions
from fontlabapp.qt.find_files.text import combo_type
from fontlabapp.core.completion import install
from fontlabapp.core.scripting import close_script_dialog, connect_guarded


def dialog_type(profile: str, qt: Any = None) -> Any:
    """Bind native classes lazily; retain the two original result policies."""
    if profile not in ("text", "bytes"):
        raise ValueError("Unknown Find Files profile")
    if qt is None:
        from fontlabapp import _native

        qt = _native("PythonQt")
    gui, core = qt.QtGui, qt.QtCore
    key = "find-font-files-" + profile

    class FindFiles(gui.QDialog):
        """One search owner; all completion routes release its I/O resources."""

        def __init__(self, parent: Any = None) -> None:
            super().__init__(parent)
            self._closed = self._closing = False
            self._connections = []
            self._search = self._browser = None
            self._paths = []
            self._profile, self._gui, self._core = profile, gui, core
            self._qt = qt
            self._completion_lifetime = install(self, key)
            self._completion_lifetime.on_destroyed.append(self._destroyed)
            self._timer = core.QTimer(self)
            try:
                self._build()
            except Exception:
                self._completion_lifetime.stop()
                for signal, slot in self._connections:
                    signal.disconnect(slot)
                self._connections.clear()
                self.deleteLater()
                raise

        def _build(self) -> None:
            """Create the complete original controls with practical source patterns."""
            home = Path.home()
            directory = home / "Documents"
            self._initial_directory = str(directory if directory.is_dir() else home)
            self.setWindowTitle(
                "Find Font Source Files" if profile == "text" else "Find Files"
            )
            self.resize(*((640, 460) if profile == "text" else (700, 300)))
            layout = gui.QVBoxLayout(self)
            self.pattern, self.containing, self.directory = (
                combo_type(qt)(self) for _ in range(3)
            )
            self.directory.setMinimumContentsLength(20)
            self.directory.setSizeAdjustPolicy(
                gui.QComboBox.AdjustToMinimumContentsLengthWithIcon
            )
            values = (
                [
                    "*.vfj",
                    "*.glyphs",
                    "*.py",
                    "*.fea",
                    "*.designspace",
                    "*.glif",
                    "*.txt",
                    "*",
                ],
                ["", "glyph", "sub ", "class "],
                [self._initial_directory],
            )
            for combo, items, label in zip(
                (self.pattern, self.containing, self.directory),
                values,
                ("Named:", "Containing text:", "In directory:"),
            ):
                combo.setEditable(True)
                combo.addItems(items)
                row = gui.QHBoxLayout()
                row.addWidget(gui.QLabel(label, self))
                row.addWidget(combo)
                layout.addLayout(row)
            if profile == "bytes":
                self.pattern.setEditText("*")
            buttons = gui.QHBoxLayout()
            layout.addLayout(buttons)
            self.browse_button = gui.QPushButton("Browse…", self)
            self.find_button = gui.QPushButton("Find", self)
            buttons.addWidget(self.browse_button)
            buttons.addWidget(self.find_button)
            self.table = gui.QTableWidget(0, 2, self)
            self.table.setHorizontalHeaderLabels(
                ["Filename", "Size (KiB)" if profile == "text" else "Size"]
            )
            self.table.horizontalHeader().setSectionResizeMode(
                0, gui.QHeaderView.Stretch
            )
            if profile == "bytes":
                self.table.setSelectionBehavior(gui.QAbstractItemView.SelectRows)
                self.table.verticalHeader().hide()
                self.table.setShowGrid(False)
            layout.addWidget(self.table)
            self.status = gui.QLabel("", self)
            layout.addWidget(self.status)
            self.progress = gui.QProgressDialog(self)
            self.progress.setWindowFlags(
                self.progress.windowFlags() | core.Qt.WindowStaysOnTopHint
            )
            self.progress.setWindowModality(core.Qt.NonModal)
            self.progress.setAutoClose(False)
            self.progress.setLabelText(
                "Reading files…" if profile == "text" else "Searching files…"
            )
            self.cancel_button = gui.QPushButton("Cancel", self.progress)
            self.progress.setCancelButton(self.cancel_button)
            for signal, callback in (
                (self.find_button.clicked, lambda *a: self._action(actions.begin)),
                (self.browse_button.clicked, lambda *a: self._action(actions.browse)),
                (self.progress.canceled, lambda *a: self._action(actions.cancel)),
                (
                    self.table.cellActivated,
                    lambda row, *a: self._action(actions.activate, row),
                ),
                (self._timer.timeout, lambda *a: self.tick()),
            ):
                connect_guarded(self, signal, callback)

        def _action(self, callback: Any, *args: Any) -> None:
            """Fence late callbacks and release search I/O on action failures."""
            if self._closed:
                return
            try:
                callback(self, *args)
            except Exception as error:  # noqa: BLE001 - contain native Qt callback faults
                actions.cancel(self)
                self.status.setText(str(error))

        def tick(self) -> None:
            """Contain callback faults and stop I/O before displaying the error."""
            try:
                actions.tick(self)
            except Exception as error:  # noqa: BLE001 - contain native Qt callback faults
                actions.cancel(self)
                self.status.setText(str(error))

        def _destroyed(self) -> None:
            """Release pure Python I/O without reading any deleted Qt wrapper."""
            self._closed = True
            if self._search is not None:
                self._search.cancel()
            self._connections.clear()

        def reject(self) -> None:
            """Permit native close reentry after the cleanup fence is set."""
            if self._closing:
                gui.QDialog.reject(self)
            elif not self._closed:
                self.close()

        def closeEvent(self, event: Any) -> None:
            """Disconnect owned slots before deferred deletion on every terminal."""
            if self._closed:
                event.accept()
                return
            self._closed = self._closing = True
            try:
                actions.cancel(self)
                children = (self.progress,) + (
                    (self._browser,) if self._browser is not None else ()
                )
                close_script_dialog(
                    self, event, key, timers=(self._timer,), children=children
                )
            finally:
                self._closing = False

    return FindFiles
