# this_file: src/fontlabapp/masters/background/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Original compact numeric controls with owned, guarded FontLab Qt lifecycle."""

from typing import Any

from fontlabapp import _native
from fontlabapp.qt.properties import value
from fontlabapp.core.scripting import (
    close_script_dialog,
    connect_guarded,
    show_script_dialog,
)


def dialog_type(mode: str) -> type:
    """Build native PythonQt only when the menu requests its numeric panel."""
    gui = _native("PythonQt").QtGui
    from fontlabapp.masters.background import model as background_tools
    from fontlabapp.core.completion import install

    class Dialog(gui.QDialog):
        def __init__(self, parent: Any = None):
            gui.QDialog.__init__(self, parent)
            self.mode = mode
            self.key = "background-" + mode
            self._connections = []
            self.last_result = None
            self.setWindowTitle(
                "Scale background" if mode == "scale" else "Shift background"
            )
            self.setFixedSize(480, 150 if mode == "shift" else 125)
            root = gui.QVBoxLayout(self)
            root.addWidget(
                gui.QLabel(
                    "Scale background content to [X]%:"
                    if mode == "scale"
                    else "Shift background content in [X] units:"
                )
            )
            self.input = gui.QLineEdit("")
            root.addWidget(self.input)
            if mode == "shift":
                root.addWidget(
                    gui.QLabel("Negative shifts left; positive shifts right.")
                )
            self.button = gui.QPushButton(
                "Scale background" if mode == "scale" else "Shift background"
            )
            self.button.setDefault(True)
            root.addWidget(self.button)
            self.status = gui.QLabel("")
            self.status.setWordWrap(True)
            root.addWidget(self.status)
            connect_guarded(self, self.button.clicked, self.apply)
            self._completion_lifetime = install(self, self.key)

        def apply(self, *args: Any) -> None:
            self.last_result = background_tools.run(
                self.mode, value(self.input, "text")
            )
            self.close()

        def closeEvent(self, event: Any) -> None:
            close_script_dialog(self, event, self.key)

    return Dialog


def show_dialog(mode: str) -> Any:
    """Retain one owned panel for each original tool; close only after success."""
    return show_script_dialog(dialog_type(mode), "background-" + mode)
