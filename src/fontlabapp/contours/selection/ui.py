# this_file: src/fontlabapp/contours/selection/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Owned modeless numeric prompt for Pedro Arilla's small-contour action."""

import sys
from typing import Any

from fontlabapp import _native
from fontlabapp.contours.selection.native import capture, execute
from fontlabapp.core.scripting import close_script_dialog, connect_guarded

QtCore, QtGui = _native("PythonQt").QtCore, _native("PythonQt").QtGui


class SmallContoursDialog(QtGui.QDialog):
    """Bind opening source, leave cancel/error unchanged, disconnect before close."""

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self._connections, self.source, self._closed = [], None, False
        self._closing = False
        self.cleanup_errors = []
        self.setWindowTitle("Select Small Contours")
        self.setModal(False)
        layout = QtGui.QVBoxLayout(self)
        layout.addWidget(
            QtGui.QLabel("Select contours with area smaller than (square font units):")
        )
        self.area = QtGui.QLineEdit("100")
        layout.addWidget(self.area)
        self.status = QtGui.QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        row = QtGui.QHBoxLayout()
        self.apply_button = QtGui.QPushButton("Select")
        self.cancel_button = QtGui.QPushButton("Close")
        row.addWidget(self.apply_button)
        row.addWidget(self.cancel_button)
        layout.addLayout(row)
        connect_guarded(self, self.apply_button.clicked, lambda *args: self.select())
        connect_guarded(
            self, self.cancel_button.clicked, lambda *args: self.close_owned()
        )
        if parent is not None:
            connect_guarded(self, parent.destroyed, lambda *args: self._destroyed())
        connect_guarded(self, self.destroyed, lambda *args: self._destroyed())
        try:
            self.source = capture(area=True)
            self.status.setText("Select changes selection in the opening layer only.")
        except Exception as error:
            self.status.setText(str(error))
            self.apply_button.setEnabled(False)

    def select(self) -> None:
        """Validate input and source; keep errors visible without closing the panel."""
        if self._closed or self.source is None:
            return
        count = execute("small", str(self.area.text), source=self.source)
        self.status.setText(f"{count} contours selected.")
        # Repeated application uses exactly the just-verified source selection.
        self.source = capture(area=True)

    def _destroyed(self) -> None:
        """Release only owned callbacks; never dereference a destroyed widget."""
        self._closed, self.source = True, None
        connections, self._connections = self._connections, []
        for signal, callback in connections:
            try:
                signal.disconnect(callback)
            except Exception as error:
                self.cleanup_errors.append(repr(error))
        windows = getattr(sys, "_fontlab_samples", {})
        if windows.get("select-small-contours") is self:
            windows.pop("select-small-contours")

    def close_owned(self) -> None:
        if not self._closed:
            self.close()

    def reject(self) -> None:
        """Route Escape through cleanup, then let native Close finish rejection."""
        if self._closing:
            QtGui.QDialog.reject(self)
        else:
            self.close_owned()

    def closeEvent(self, event: Any) -> None:
        self._closed, self._closing, self.source = True, True, None
        try:
            close_script_dialog(self, event, "select-small-contours")
        finally:
            self._closing = False
