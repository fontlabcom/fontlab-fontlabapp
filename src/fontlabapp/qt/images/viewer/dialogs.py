# this_file: src/fontlabapp/qt/images/viewer/dialogs.py
# SPDX-License-Identifier: Apache-2.0
"""Asynchronous owned file, printer and help dialogs; no application event loop."""
from typing import Any
from fontlabapp.qt.images.viewer.io import render
from fontlabapp.core.signals.scope import Scope
from fontlabapp.qt.properties import value


def retain(panel: Any, dialog: Any, callback: Any = None, *, modal: bool = True) -> Any:
    core = panel._core
    dialog.setAttribute(core.Qt.WA_DeleteOnClose, False)
    dialog.setAttribute(core.Qt.WA_QuitOnClose, False)
    dialog.setWindowModality(core.Qt.WindowModal if modal else core.Qt.NonModal)
    panel._dialogs.append(dialog)
    dialog.setWindowFlags(dialog.windowFlags() | core.Qt.WindowStaysOnTopHint)
    if callback is not None:
        panel.scope.connect(dialog.accepted, lambda *args: callback() if not panel.closing else None)
    dialog.open() if modal else dialog.show()
    return dialog


def choose(panel: Any) -> Any:
    gui = panel._gui
    dialog = gui.QFileDialog(panel)
    dialog.setWindowTitle("Open File" if panel.part == 3 else "Open")
    dialog.setOption(gui.QFileDialog.DontUseNativeDialog, True)
    dialog.setFileMode(gui.QFileDialog.ExistingFile)
    dialog.setDirectory(str(panel.workspace.directory()))

    def accepted() -> None:
        files = list(dialog.selectedFiles())
        if files:
            panel.load(str(files[0]))

    return retain(panel, dialog, accepted, modal=panel.part == 2)


def print_dialog(panel: Any) -> Any:
    gui = panel._gui
    if panel.part == 2:
        printer = gui.QPrinter()
        dialog = gui.QPrintDialog(printer, panel)
        panel._devices.append(printer)
        # QPrintDialog borrows this external native value. Keep a dedicated
        # terminal lease until its QObject destruction, including parent death.
        lease = Scope(panel.failure)
        panel._leases.append(lease)
        def released(*args: Any) -> None:
            panel._devices[:] = [item for item in panel._devices if item is not printer]
            panel._leases.remove(lease)
            lease.finish(destroyed=True)
        try:
            lease.connect(dialog.destroyed, released, closing=True)
        except Exception:
            panel._leases.remove(lease)
            dialog.deleteLater()
            panel._core.QCoreApplication.sendPostedEvents(dialog, panel._core.QEvent.DeferredDelete)
            raise
    else:
        dialog = gui.QPrintDialog(panel)
        printer = dialog.printer()
        printer.setOutputFormat(gui.QPrinter.PdfFormat)
        printer.setOutputFileName(str(panel.workspace.directory() / "output.pdf"))

    def accepted() -> None:
        if panel.part == 3:
            try:
                panel.workspace.destination(value(printer, "outputFileName"))
                if value(printer, "outputFormat") != gui.QPrinter.PdfFormat:
                    raise ValueError("Choose PDF output inside this viewer's temporary directory.")
            except ValueError as error:
                panel.failure(error)
                panel.message("Print path refused", str(error))
                return
        render(panel.part, panel.image, panel._pixmap, printer, panel._core, gui)

    return retain(panel, dialog, accepted)


def message(panel: Any, title: str, text: str) -> Any:
    box = panel._gui.QMessageBox(panel)
    box.setWindowTitle(title)
    box.setText(text)
    return retain(panel, box, modal=panel.part == 3)
