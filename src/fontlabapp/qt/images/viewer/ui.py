# this_file: src/fontlabapp/qt/images/viewer/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Complete source-distinct reference image panels with owned retryable teardown."""
import sys
from pathlib import Path
from typing import Any
from fontlabapp.core.signals.scope import Scope
from fontlabapp.qt.images.viewer.model import scaled_size, scroll_value
from fontlabapp.qt.images.viewer.controls import build
from fontlabapp.qt.images.viewer.io import Workspace
from fontlabapp.qt.properties import value


def panel_type(core: Any, gui: Any, part: int) -> type:
    if part not in (2, 3):
        raise ValueError("Choose image viewer profile2 or3.")
    base = gui.QWidget if part == 2 else gui.QMainWindow

    class ReferenceImages(base):
        def __init__(self, parent: Any, *, temporary_parent: Path | None = None) -> None:
            base.__init__(self, parent, core.Qt.Window | core.Qt.WindowStaysOnTopHint)
            self._core, self._gui, self.part = core, gui, part
            self.closed = self.dead = self.closing = False
            self.image = self._pixmap = self.status = None
            self.scale, self.fit, self.last_error = (1.0 if part == 2 else 0.0), False, ""
            self.commands, self._dialogs, self._devices, self._leases = {}, [], [], []
            self.key, self.workspace = f"reference_image_{part}", Workspace(temporary_parent)
            self.scope, self.closers, self.terminal = Scope(self.failure), Scope(self.failure), Scope(self.failure)
            try:
                self.terminal.connect(self.destroyed, lambda *args: self.dispose(destroyed=True), closing=True)
                build(self, core, gui)
            except BaseException:
                if self.dispose():
                    self.deleteLater()
                else:
                    sys.__dict__.setdefault("_fontlab_samples", {})[self.key] = self
                    self.show()
                raise

        def failure(self, error: Exception) -> None:
            if self.closed or self.dead:
                return
            self.last_error = str(error)
            if self.status is not None:
                try:
                    self.status.setText(self.last_error)
                except Exception:
                    pass  # Diagnostics must never escape a native signal callback.

        def update_actions(self) -> None:
            for key in ("zoom_in", "zoom_out", "normal"):
                self.commands[key].setEnabled(self.image is not None and not self.fit)
            for key in ("print", "fit"):
                self.commands[key].setEnabled(self.image is not None)

        def load(self, path: str) -> bool:
            if self.closing:
                return False
            image = gui.QImage(path)
            if value(image, "isNull"):
                self.failure(ValueError("Cannot read this image."))
                return False
            pixmap = gui.QPixmap.fromImage(image)
            self.image_label.setPixmap(pixmap)
            self.image, self._pixmap, self.scale = image, pixmap, 1.0
            self.image_label.setScaledContents(True)
            self.update_actions()
            if not self.fit:
                self.normal()
            return True

        def zoom(self, factor: float) -> None:
            if self.closing or self.image is None or (part == 2 and self.fit):
                return
            self.scale *= factor
            size = self.image if part == 2 else self._pixmap
            self.image_label.resize(*scaled_size(value(size, "width"), value(size, "height"), self.scale))
            for bar in (self.scroll_area.horizontalScrollBar(), self.scroll_area.verticalScrollBar()):
                bar.setValue(scroll_value(factor, value(bar, "value"), value(bar, "pageStep")))
            if part == 3:
                self.commands["zoom_in"].setEnabled(self.scale < 3)
                self.commands["zoom_out"].setEnabled(self.scale > .333)

        def normal(self) -> None:
            if self.closing or self.image is None:
                return
            self.scale = 1.0
            if part == 3:
                self.image_label.adjustSize()
            elif not self.fit:
                self.image_label.resize(value(self.image, "width"), value(self.image, "height"))

        def toggle_fit(self) -> None:
            if self.closing or self.image is None:
                return
            self.fit = not self.fit if part == 2 else value(self.commands["fit"], "isChecked")
            self.scroll_area.setWidgetResizable(self.fit)
            if not self.fit:
                if part == 3:
                    self.normal()
                else:
                    self.image_label.resize(*scaled_size(value(self.image, "width"), value(self.image, "height"), self.scale))
            self.update_actions()

        def open_file(self) -> Any:
            if not self.closing:
                from fontlabapp.qt.images.viewer.dialogs import choose
                return choose(self)

        def print_image(self) -> Any:
            if not self.closing and self.image is not None:
                from fontlabapp.qt.images.viewer.dialogs import print_dialog
                return print_dialog(self)

        def message(self, title: str, text: str) -> Any:
            if not self.closing:
                from fontlabapp.qt.images.viewer.dialogs import message
                return message(self, title, text)

        def about(self) -> None:
            self.message("About Font Reference Image Viewer", "Open artwork to inspect its pixels. Zoom and Fit use QLabel and QScrollArea. Print draws the image with QPainter." + (" Bounded Zoom preserves the original aspect-fit temporary PDF workflow." if part == 3 else " Free zoom preserves native-size printing."))

        def dispose(self, *, destroyed: bool = False) -> bool:
            if self.dead:
                return True
            self.closing = True
            if destroyed:
                self.dead = self.closed = True
                for scope in (self.scope, self.closers, self.terminal):
                    scope.finish(destroyed=True)
                try:
                    self.workspace.close()
                except Exception as error:
                    self.last_error = str(error)
            else:
                self.workspace.verify()
                if not self.scope.finish():
                    return False
                for dialog in self._dialogs:
                    dialog.close()
                    dialog.deleteLater()
                    core.QCoreApplication.sendPostedEvents(dialog, core.QEvent.DeferredDelete)
                self._dialogs.clear()
                self._devices.clear()
                self.workspace.close()
                if not self.closers.finish():
                    return False
                self.closed = True
            self.image = self._pixmap = None
            registry = getattr(sys, "_fontlab_samples", {})
            if registry.get(self.key) is self:
                registry.pop(self.key)
            return True

        def keyPressEvent(self, event: Any) -> None:
            if event.key() == core.Qt.Key_Escape:
                self.close()
                event.accept()
            else:
                base.keyPressEvent(self, event)

        def closeEvent(self, event: Any) -> None:
            try:
                if not self.dispose():
                    event.ignore()
                    return
                base.closeEvent(self, event)
                self.deleteLater()
            except Exception as error:
                self.failure(error)
                event.ignore()

    return ReferenceImages
