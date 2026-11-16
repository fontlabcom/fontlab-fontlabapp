# this_file: src/fontlabapp/fontui/reference_images.py
# SPDX-License-Identifier: Apache-2.0
"""Reference Image Viewer app: the original viewer embedded in the shared shell.

What: one ``AppShell`` (no preview) with an Image tab holding the original
read-only reference image viewer and the shared About tab. Open, zoom, fit,
normal size and print stay the viewer's own commands; nothing writes to a font.
Close: the viewer's Exit, Escape, window close and the shell Close button all
close the shell; a refused viewer cleanup keeps the shell open for a retry.
"""

from threading import current_thread, main_thread
from typing import Any

from PythonQt import QtCore, QtGui

from fontlabapp.qt.images.viewer.ui import panel_type

from .appshell import AppShell
from .lifecycle import Owned

_HANDLES: list[Any] = []
ABOUT = (
    "Reference Image Viewer: open artwork to inspect its pixels, zoom, fit and print.\n"
    "Source: https://github.com/fontlabcom/fontlab-fontlabapp\n"
    "Menus: https://github.com/fontlabcom/fontlab-python-scriptmix\n"
    "FontLab App contributors (Apache-2.0). See NOTICE for component licences."
)


class ImageShell(AppShell):
    """The shell; a completed close releases the module handle."""

    def close(self) -> None:
        super().close()
        if self in _HANDLES:
            _HANDLES.remove(self)


class ImagesTab(Owned):
    """Owns the embedded original viewer; closing it is retryable."""

    def __init__(self, shell: Any, parent: Any) -> None:
        super().__init__(parent)
        self.shell = shell
        kind = panel_type(QtCore, QtGui, 2)

        class Embedded(kind):
            def closeEvent(self, event: Any) -> None:
                # Exit, Escape and window close all end the shell, never only the viewer.
                event.ignore()
                shell._run_action("close")

        self.viewer = Embedded(self.widget)
        self.viewer.setWindowFlags(QtCore.Qt.Widget)
        self.layout.addWidget(self.viewer)

    def close(self) -> None:
        if not self._close_complete:
            if not self.viewer.dispose():
                raise RuntimeError("Reference image viewer cleanup is incomplete")
            self.viewer.hide()
            self.viewer.deleteLater()
        super().close()


class ImageTab:
    title = "Image"

    def build(self, shell: Any) -> Any:
        shell.images = ImagesTab(shell, shell.widget)
        return shell.images


def show(parent: Any = None) -> Any:
    """Open the Reference Image Viewer app on the main UI thread and return its shell."""
    if current_thread() is not main_thread():
        raise RuntimeError("Open reference image viewers on the main UI thread.")
    shell = ImageShell("Reference Image Viewer", None, parent=parent)
    _HANDLES.append(shell)
    try:
        shell.add_tab(ImageTab())
        shell.set_about(ABOUT)
        shell.show()
    except BaseException as error:
        try:
            shell.close()
        except Exception as cleanup:  # noqa: BLE001 - retain the failed owner visibly
            error.add_note(f"Reference Image Viewer cleanup incomplete; owner retained: {cleanup}")
        raise
    return shell
