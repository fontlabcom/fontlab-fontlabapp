# this_file: src/fontlabapp/metrics/canvas_rsb/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Own one modeless foreground RSB overlay; never own a font or Glyph window.

This is an explicit FontLab adaptation of RSBline behavior. Direction is a
visible choice; Glyphs text-tool gating and background ordering are not claimed.
Close and toggle-off stop polling, disconnect callbacks and remove the overlay.
"""

from importlib import import_module
from typing import Any

from fontlabapp.glyphs.names.ui import NamesDialog, QtCore, QtGui
from fontlabapp.core.controls import FontLab
from fontlabapp.core.scripting import current_package

TITLE, KEY = "Right Sidebearing Line", "canvas_right_sidebearing_line"
api = import_module("fontlabapp.metrics.canvas_rsb.model")


class CanvasRSBDialog(NamesDialog):
    """Bind one font/master/window; reopen the panel to follow another context."""

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent, TITLE, KEY)
        self.app = self.glyph_view = self.drawing = None
        self._window_slot = None
        self.binding = None
        self.records: tuple[api.Marker, ...] = ()
        self.paint_error = ""
        self.subtitle.setText(
            "Foreground adaptation · Choose LTR or RTL explicitly. "
            "Draws in this Glyph window across tools; does not edit the font."
        )
        self.enabled_box = QtGui.QCheckBox("Enabled")
        self.enabled_box.setChecked(True)
        self.root.addWidget(self.enabled_box)
        form = QtGui.QFormLayout()
        self.direction = QtGui.QComboBox()
        self.direction.addItems(
            ["Left to right · right edge", "Right to left · left edge"]
        )
        form.addRow("Direction", self.direction)
        self.root.addLayout(form)
        self.status = QtGui.QLabel()
        self.status.setWordWrap(True)
        self.root.addWidget(self.status)
        self.close_button = QtGui.QPushButton("Close")
        self.root.addWidget(self.close_button)
        self.color = self.palette.color(QtGui.QPalette.Highlight).name()
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(250)
        self._connect(self.enabled_box.toggled, lambda *a: self.toggle())
        self._connect(self.direction.currentIndexChanged, lambda *a: self.refresh())
        self._connect(self.close_button.clicked, lambda *a: self.close())
        self._connect(self.timer.timeout, lambda *a: self.refresh())
        self.toggle()

    def context(self) -> tuple[Any, Any]:
        """Resolve fresh active handles before touching any cached native pointer."""
        package = current_package()
        if package is None:
            raise ValueError(
                "Open a font and its Glyph window, then reopen this panel."
            )
        window = self.app.glyph_window()
        canvas = window.canvas
        identity = package.id, package.master, canvas.id
        if self.binding is not None and identity != self.binding:
            raise ValueError("Font, master or Glyph window changed; reopen this panel.")
        if not window.widget.isVisible():
            raise ValueError("The bound Glyph window is closed; reopen this panel.")
        self.binding = identity
        return package, window

    def toggle(self) -> None:
        """Toggle only owned resources; a fresh activation must pass all guards."""
        if not self.enabled_box.isChecked():
            try:
                self.stop()
                self.status.setText("Overlay off")
            except Exception as error:  # noqa: BLE001 - native cleanup boundary
                self.fail(error)
            return
        if self.drawing is not None:
            self.refresh()
            return
        try:
            self.stop()
            self.paint_error = ""
            self.app = FontLab()
            _, self.glyph_view = self.context()
            self.refresh()
            if not self.enabled_box.isChecked():
                return
            self.drawing = self.glyph_view.draw(self.paint, coordinates="pixels")
            self._window_slot = lambda *a: self.window_gone()
            self.glyph_view.widget.destroyed.connect(self._window_slot)
            self.timer.start()
        except Exception as error:  # noqa: BLE001 - contain modeless activation
            self.fail(error)

    def refresh(self) -> None:
        """Publish only two agreeing complete bounded scans, outside painting."""
        if not self.enabled_box.isChecked():
            return
        try:
            if self.paint_error:
                raise RuntimeError(self.paint_error)
            package, window = self.context()
            direction = 0 if self.direction.currentIndex == 0 else 2
            records = api.capture(window.canvas, package, direction)
            if records != api.capture(window.canvas, package, direction):
                raise ValueError("Glyph layout changed during refresh; enable again.")
            self.context()
            if self.drawing is not None:
                self.drawing.raise_if_failed()
            if records != self.records:
                self.records = records
                if self.drawing is not None:
                    self.drawing.refresh()
            self.status.setText(
                f"{package.elidedName} · {package.master} · {len(records)} glyph occurrences"
            )
        except Exception as error:  # noqa: BLE001 - contain timer and native reads
            self.fail(error)

    def paint(self, painter: Any) -> None:
        """Borrow the Drawing painter; defer any teardown until after its end()."""
        if not self.records:
            return
        try:
            api.paint(painter, self.records, self.color)
        except Exception as error:  # noqa: BLE001 - never unwind into native Qt
            self.paint_error = str(error)
            self.records = ()

    def stop(self) -> None:
        """Disconnect native destruction before closing owned drawings."""
        self.timer.stop()
        self.records = ()
        window, slot, app = self.glyph_view, self._window_slot, self.app
        self.drawing = None
        errors = []
        try:
            if window is not None and slot is not None:
                window.widget.destroyed.disconnect(slot)
            self.glyph_view = self._window_slot = None
        except Exception as error:  # noqa: BLE001 - native cleanup boundary
            errors.append(str(error))
        if app is not None:
            try:
                app.close()
                self.app = None
            except Exception as error:  # noqa: BLE001 - retain resources for retry
                errors.append(str(error))
        if errors:
            raise RuntimeError("; ".join(errors))

    def fail(self, error: Exception) -> None:
        """Leave the complete panel closable after an empty, failed or stale read."""
        try:
            self.stop()
        except Exception as failure:  # noqa: BLE001 - retain cleanup failures visibly
            error = RuntimeError(f"{error}; overlay cleanup failed: {failure}")
        blocked = self.enabled_box.blockSignals(True)
        try:
            self.enabled_box.setChecked(False)
        finally:
            self.enabled_box.blockSignals(blocked)
        self.status.setText("Error: " + str(error))

    def invalidate(self) -> None:
        """The shared signal guard clears this overlay rather than other panels."""
        self.stop()

    def window_gone(self) -> None:
        """Native parent destruction has already removed the overlay child."""
        self.glyph_view = self._window_slot = None
        self.fail(ValueError("The bound Glyph window closed; reopen this panel."))

    def closeEvent(self, event: Any) -> None:
        """Release the app/drawing before shared timer and signal destruction."""
        try:
            self.stop()
        except Exception as error:  # noqa: BLE001 - Qt close callback boundary
            self.fail(error)
            if self._window_slot is not None or self.app is not None:
                event.ignore()
                return
        super().closeEvent(event)
