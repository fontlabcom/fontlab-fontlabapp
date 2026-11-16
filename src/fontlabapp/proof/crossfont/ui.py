# this_file: src/fontlabapp/proof/crossfont/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Own two lazy, literal, selectable snapshot reports without changing user Output."""
from typing import Any
from time import monotonic
from fontlabapp import _native
import fontlabapp.proof.crossfont.model as model
import fontlabapp.proof.crossfont.native as native
from fontlabapp.core.completion import install
from fontlabapp.core.scripting import close_script_dialog, show_script_dialog
from fontlabapp.proof.text_holder.editor import editor_type, literal_text

def dialog_type(composites: bool, qt: Any = None) -> type:
    """Bind the complete original output to injected Qt or the actual PythonQt host."""
    qt = _native("PythonQt") if qt is None else qt
    gui, core = qt.QtGui, qt.QtCore
    key = "composite_differences" if composites else "glyph_set_differences"
    render = model.composite_text if composites else model.glyph_sets_text

    class Output(editor_type(qt)):
        """Native read-only interaction plus literal selection MIME export."""
        def inputMethodEvent(self, event: Any) -> None:
            event.ignore()

    class Dialog(gui.QDialog):
        """Snapshot the source-defined font domain on each explicit Refresh."""
        def __init__(self, parent: Any = None) -> None:
            gui.QDialog.__init__(self, parent)
            self._connections = []
            self._closed = self._closing = False
            self.KEY = key
            self._completion_lifetime = install(self, key)
            self._completion_lifetime.on_destroyed.append(self.retire)
            try:
                self.setWindowTitle("Report Composite Differences" if composites else "Report Glyph Set Differences")
                self.setWindowFlags(core.Qt.Window | core.Qt.WindowTitleHint | core.Qt.WindowSystemMenuHint | core.Qt.WindowCloseButtonHint | core.Qt.WindowMinimizeButtonHint)
                self.setModal(False)
                self.resize(720, 480)
                root = gui.QVBoxLayout(self)
                self.output = Output(self)
                self.output.setReadOnly(True)
                root.addWidget(self.output)
                footer = gui.QHBoxLayout()
                self.status = gui.QLabel()
                self.status.setWordWrap(True)
                self.refresh_button = gui.QPushButton("Refresh")
                self.close_button = gui.QPushButton("Close")
                for widget in (self.status, self.refresh_button, self.close_button):
                    footer.addWidget(widget)
                root.addLayout(footer)
                for signal, slot in ((self.refresh_button.clicked, lambda *args: self.refresh()), (self.close_button.clicked, lambda *args: None if self._closed else self.close())):
                    signal.connect(slot)
                    self._connections.append((signal, slot))
                self.refresh()
            except BaseException:
                self._completion_lifetime.stop()
                self.deleteLater()
                raise

        def retire(self) -> None:
            """Fence retained callbacks before parent/native child destruction."""
            self._closed = True
            for signal, slot in reversed(tuple(self._connections)):
                try:
                    signal.disconnect(slot)
                except Exception:
                    pass
            self._connections.clear()

        def refresh(self) -> None:
            """Publish a whole stable snapshot, or show a contained read diagnosis."""
            if self._closed:
                return
            try:
                deadline = monotonic() + 3.5
                snapshot = native.capture(composites=composites, deadline=deadline)
                text = render(snapshot, deadline=deadline)
                if self._closed:
                    return
                self.output.setPlainText(text)
                if literal_text(self.output) != text:
                    raise ValueError("The host cannot preserve the complete report text")
                self.status.setText("Current font → first other open font." if composites else "Current font → every other open font.")
            except Exception as error:
                if not self._closed:
                    self.output.clear()
                    self.status.setText(str(error))

        def reject(self) -> None:
            if self._closing:
                gui.QDialog.reject(self)
            elif not self._closed:
                self.close()

        def closeEvent(self, event: Any) -> None:
            self._closing = True
            try:
                close_script_dialog(self, event, key)
            except BaseException:
                if self._completion_lifetime.closed:
                    self._completion_lifetime = install(self, key)
                    self._completion_lifetime.on_destroyed.append(self.retire)
                raise
            else:
                self._closed = True
            finally:
                self._closing = False
    return Dialog

def open_report(*, composites: bool = False) -> Any:
    """Replace only the same owned report, keeping the other report independent."""
    key = "composite_differences" if composites else "glyph_set_differences"
    return show_script_dialog(dialog_type(composites), key)
