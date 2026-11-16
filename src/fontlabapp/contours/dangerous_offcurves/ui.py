# this_file: src/fontlabapp/contours/dangerous_offcurves/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Owned complete finding text for the full-font Dangerous Offcurves action."""

from typing import Any

import fontlabapp.contours.dangerous_offcurves.model as model
import fontlabapp.contours.dangerous_offcurves.native as api
from fontlabapp import _native
from fontlabapp.core.completion import install
from fontlabapp.core.scripting import close_script_dialog


def dialog_type(qt: Any = None) -> type:
    """Bind the tiny window lazily to PythonQt or an explicitly injected Qt test API."""
    qt = _native("PythonQt") if qt is None else qt
    gui, core = qt.QtGui, qt.QtCore

    class Dialog(gui.QDialog):
        """Own complete selectable finding text; never clear the user's Output."""

        def __init__(self, parent: Any = None) -> None:
            """Read the complete snapshot before allocating native child controls."""
            text = model.render(api.run())
            gui.QDialog.__init__(self, parent)
            self._connections = []
            self._closed = self._closing = False
            self._completion_lifetime = install(self, model.KEY)
            try:
                self.setWindowTitle("Dangerous Offcurves")
                self.setWindowFlags(
                    core.Qt.Window
                    | core.Qt.WindowTitleHint
                    | core.Qt.WindowSystemMenuHint
                    | core.Qt.WindowCloseButtonHint
                    | core.Qt.WindowMinMaxButtonsHint
                )
                self.setModal(False)
                self.resize(620, 480)
                root = gui.QVBoxLayout(self)
                root.setContentsMargins(10, 10, 10, 10)
                self.output = gui.QPlainTextEdit(self)
                self.output.setReadOnly(True)
                self.output.setPlainText(text)
                root.addWidget(self.output)
            except BaseException:
                self._completion_lifetime.stop()
                self.deleteLater()
                raise

        def reject(self) -> None:
            """Escape uses owned Close; native Close rejection can finish reentrantly."""
            if self._closing:
                gui.QDialog.reject(self)
            elif not self._closed:
                self.close()

        def closeEvent(self, event: Any) -> None:
            """Disconnect completion before native close and deferred deletion."""
            self._closed = self._closing = True
            try:
                close_script_dialog(self, event, model.KEY)
            finally:
                self._closing = False

    return Dialog
