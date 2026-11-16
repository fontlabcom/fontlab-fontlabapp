# this_file: src/fontlabapp/masters/point_counts/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Plain normal-window snapshot with the original Point Counter dimensions."""

from typing import Any

import fontlabapp.masters.point_counts.model as model
import fontlabapp.masters.point_counts.native as api
from fontlabapp import _native
from fontlabapp.core.completion import install
from fontlabapp.core.scripting import close_script_dialog
from fontlabapp.proof.text_holder.editor import editor_type, literal_text


def dialog_type(qt: Any = None) -> type:
    """Bind the tiny window lazily to PythonQt or an explicitly injected Qt test API."""
    qt = _native("PythonQt") if qt is None else qt
    gui, core = qt.QtGui, qt.QtCore

    class Output(editor_type(qt)):
        """Reuse literal MIME export without the editable helper's IME ingress."""

        def inputMethodEvent(self, event: Any) -> None:
            """Refuse preedit and commit input; this report is permanently read-only."""
            event.ignore()

    class Dialog(gui.QDialog):
        """Own a fixed400×300 read-only snapshot; never clear the user's Output."""

        def __init__(self, parent: Any = None) -> None:
            """Read the complete snapshot before allocating native child controls."""
            text = model.render(api.capture())
            gui.QDialog.__init__(self, parent)
            self._connections = []
            self._closed = self._closing = False
            self._completion_lifetime = install(self, model.KEY)
            try:
                self.setWindowTitle("Point Counter")
                self.setWindowFlags(
                    core.Qt.Window
                    | core.Qt.WindowTitleHint
                    | core.Qt.WindowSystemMenuHint
                    | core.Qt.WindowCloseButtonHint
                    | core.Qt.WindowMinimizeButtonHint
                )
                self.setModal(False)
                self.setFixedSize(400, 300)
                root = gui.QVBoxLayout(self)
                root.setContentsMargins(10, 10, 10, 10)
                self.output = Output(self)
                self.output.setReadOnly(True)
                self.output.setPlainText(text)
                if literal_text(self.output) != text:
                    raise ValueError("The host cannot preserve the complete report text")
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
