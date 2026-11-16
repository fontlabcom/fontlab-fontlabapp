# this_file: src/fontlabapp/proof/reports/snapshot_ui.py
# SPDX-License-Identifier: Apache-2.0
"""Share the owned read-only report lifecycle used by three script panels."""

import sys
from collections.abc import Callable
from typing import Any

from fontlabapp.glyphs.names.ui import NamesDialog, QtGui


class SnapshotTextDialog(NamesDialog):
    """Own one modeless read-only snapshot and all its callback connections."""

    def __init__(
        self,
        parent: Any,
        title: str,
        key: str,
        description: str,
        capture: Callable[[], Any],
        render: Callable[[Any], str],
        status: Callable[[Any], str],
    ) -> None:
        """Create Close and diagnostic output before the first native capture."""
        super().__init__(parent, title, key)
        self._capture, self._render, self._status = capture, render, status
        self._closed = False
        self._disconnect_errors: list[str] = []
        self.report = None
        self.setModal(False)
        self.resize(620, 480)
        self.subtitle.setText(description)
        self.output = QtGui.QPlainTextEdit()
        self.output.setReadOnly(True)
        self.root.addWidget(self.output, 1)
        footer = QtGui.QHBoxLayout()
        self.status = QtGui.QLabel()
        self.status.setWordWrap(True)
        self.refresh_button = QtGui.QPushButton("Refresh")
        self.close_button = QtGui.QPushButton("Close")
        footer.addWidget(self.status, 1)
        footer.addWidget(self.refresh_button)
        footer.addWidget(self.close_button)
        self.root.addLayout(footer)
        self._connect(self.refresh_button.clicked, lambda *args: self.refresh())
        self._connect(
            self.close_button.clicked,
            lambda *args: None if self._closed else self.close(),
        )
        self._completion_lifetime.on_destroyed.append(self._destroyed)
        if parent is not None:
            self._connect(parent.destroyed, lambda *args: self._destroyed())
        self.refresh()

    def refresh(self) -> None:
        """Replace the whole snapshot, or clear it and show the read failure."""
        if self._closed:
            return
        self.report = None
        try:
            self.output.clear()
            report = self._capture()
            if self._closed:
                return
            rendered = self._render(report)
            if self._closed:
                return
            status = self._status(report)
            if self._closed:
                return
            self.output.setPlainText(rendered)
            if self._closed:
                return
            self.report = report
            self.status.setText(status)
        except Exception as error:  # noqa: BLE001 - contain native slot/teardown failures
            self.slot_error = repr(error)
            if not self._closed:
                self.output.clear()
                self.status.setText(str(error))

    def _destroyed(self) -> None:
        """Disconnect Python targets before native parent/child destruction."""
        self._closed = True
        self.report = None
        self._capture = self._render = self._status = None
        self._completion_lifetime.stop()
        for signal, slot in reversed(tuple(self._connections)):
            try:
                signal.disconnect(slot)
            except Exception as error:  # noqa: BLE001 - contain native slot/teardown failures
                self._disconnect_errors.append(repr(error))
        self._connections.clear()
        windows = getattr(sys, "_fontlab_samples", {})
        if windows.get(self.KEY) is self:
            windows.pop(self.KEY)

    def closeEvent(self, event: Any) -> None:
        """Fence retained callbacks before the existing owned Close lifecycle."""
        self._closed = True
        self.report = None
        self._capture = self._render = self._status = None
        super().closeEvent(event)
