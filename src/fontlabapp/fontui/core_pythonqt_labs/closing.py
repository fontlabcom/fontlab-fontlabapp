# this_file: src/fontlabapp/fontui/core_pythonqt_labs/closing.py
# SPDX-License-Identifier: Apache-2.0
"""Route an embedded lesson's local Close/Escape through its whole lab owner."""
from PythonQt import QtCore, QtGui

from fontlabapp.qt.properties import value


class CloseFilter(QtGui.QWidget):
    """Defer Close off the child's event stack so its cleanup still runs once."""

    def __init__(self, shell, widget):
        super().__init__(shell.widget)
        self.shell = shell
        self.pending = False
        widget.installEventFilter(self)
        self.hide()

    def eventFilter(self, watched, event):
        if self.shell._closing or self.shell.closed:
            return False
        closing = value(event, "type") == QtCore.QEvent.Close
        escape = value(event, "type") == QtCore.QEvent.KeyPress and value(event, "key") == QtCore.Qt.Key_Escape
        if not (closing or escape):
            return False
        event.ignore()
        if not self.pending:
            self.pending = True
            QtCore.QTimer.singleShot(0, self.finish)
        return True

    def finish(self):
        self.pending = False
        self.shell._run_action('close')

    def route(self, callback):
        """Route a controller-owned Close button which has no QWidget Close event."""
        def close(*args, **kwargs):
            if self.shell._closing:
                return callback(*args, **kwargs)
            if not self.pending:
                self.pending = True
                QtCore.QTimer.singleShot(0, self.finish)
            return False
        return close
