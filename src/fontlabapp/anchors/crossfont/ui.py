# this_file: src/fontlabapp/anchors/crossfont/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Owned complete cross-font anchor-copy dialog; no hidden document activation."""

import sys
from typing import Any

from fontlabapp.anchors.crossfont.controls import build, options, reset_layers
from fontlabapp.core.signals.scope import Scope
from fontlabapp.qt.properties import value

KEY = "crossfont-copy-anchors"


def panel_type(core: Any, gui: Any) -> type:
    """Inject the real Qt binding; import outside FontLab without loading Qt."""

    class CopyAnchors(gui.QDialog):
        def __init__(self, parent: Any, backend: Any) -> None:
            """Own the complete dialog and retain recoverable constructor failures."""
            gui.QDialog.__init__(self, parent)
            self.setWindowFlags(self.windowFlags() | core.Qt.WindowStaysOnTopHint)
            self.backend, self.fonts, self.last_result = backend, (), None
            self.closed = self.dead = self.busy = self.completing = False
            self.last_error = ""
            self.status = self.copy_button = self.details = None
            self.signals, self.terminal = Scope(self.failure), Scope(self.failure)
            try:
                self.terminal.connect(
                    self.destroyed,
                    lambda *args: self.dispose(destroyed=True),
                    closing=True,
                )
                self.terminal.connect(
                    self.finished, lambda *args: self.completed(), closing=True
                )
                build(self, core, gui)
                self.refresh_fonts()
            except BaseException:
                if self.close() is False:
                    sys.__dict__.setdefault("_fontlab_samples", {})[KEY] = self
                    self.show()
                raise

        def failure(self, error: Exception) -> None:
            """Contain callback errors and prevent stale success publication."""
            self.last_error = f"{type(error).__name__}: {error}"
            self.last_result = None
            if self.status is not None and not self.dead:
                self.status.setText("Copy failed. See details.")
                if self.details is not None:
                    self.details.setPlainText(self.last_error)
                    self.details.show()

        def chosen(self, side: str) -> Any:
            """Resolve the selected registered identity without basename ambiguity."""
            index = int(value(getattr(self, side + "_font"), "currentIndex"))
            if not 0 <= index < len(self.fonts):
                raise ValueError("Refresh the open-font lists before copying.")
            return self.fonts[index]

        def refresh_fonts(self) -> None:
            """Refresh both selectors and reset their layer choices as in the original."""
            if self.closed or self.busy:
                return
            self.busy = True
            try:
                self.fonts = self.backend.fonts()
                for side in ("source", "destination"):
                    combo = getattr(self, side + "_font")
                    combo.clear()
                    combo.addItems(
                        [
                            f"{row.label or 'Untitled'} [#{row.identity}]"
                            for row in self.fonts
                        ]
                    )
                    reset_layers(getattr(self, side + "_layer"))
                self.copy_button.setEnabled(bool(self.fonts))
                self.status.setText(
                    "Font lists updated!" if self.fonts else "No open font files found!"
                )
                self.last_result = None
                self.details.clear()
                self.details.hide()
            finally:
                self.busy = False

        def refresh_layers(self, side: str) -> None:
            """Refresh only the chosen side while retaining the other selection."""
            if self.closed or self.busy:
                return
            self.busy = True
            try:
                selected = self.chosen(side).identity
                fresh = self.backend.fonts()
                row = next((r for r in fresh if r.identity == selected), None)
                if row is None:
                    raise ValueError("The chosen font closed; refresh font lists.")
                combo = getattr(self, side + "_layer")
                reset_layers(combo)
                combo.addItems(list(row.masters))
                self.status.setText("Layers list updated!")
            finally:
                self.busy = False

        def copy(self) -> None:
            """Dispatch every current original option once, retaining skips and failures."""
            if self.closed or self.busy:
                return
            self.busy = True
            self.last_result = None
            try:
                a, b = self.chosen("source"), self.chosen("destination")
                result = self.backend.copy(
                    a.identity,
                    b.identity,
                    str(value(self.source_layer, "currentText")),
                    str(value(self.destination_layer, "currentText")),
                    self.selected_glyphs.isChecked(),
                    options(self),
                )
                if self.closed:
                    return
                self.last_result = result
                self.last_error = ""
                summary = f"Copied {result['anchors']} anchors across {result['layers']} layers."
                lines = list(result["skipped"])
                lines.extend(
                    f"Zero source advance: {name}/{anchor}; used absolute x."
                    for name, anchor in result["zero_advance"]
                )
                if not result["anchors"]:
                    summary = "Nothing to process! " + summary
                self.status.setText(summary)
                self.details.setPlainText("\n".join(lines))
                self.details.setVisible(bool(lines))
            finally:
                self.busy = False

        def completed(self) -> None:
            """Route native Accept/Reject/Done through the owned close path."""
            if self.closed or self.completing:
                return
            self.completing = True
            try:
                accepted = self.close()
                if not self.closed and accepted is not False:
                    event = gui.QCloseEvent()
                    type(self).closeEvent(self, event)
                    accepted = event.isAccepted()
                if accepted is False:
                    self.show()
            finally:
                self.completing = False

        def dispose(self, *, destroyed: bool = False) -> bool:
            """Fence late work, drain exact signal pairs and retain refused cleanup."""
            self.closed, self.dead, self.backend = True, destroyed, None
            self.fonts = ()
            self.last_result = None
            if not self.signals.finish(destroyed=destroyed):
                return False
            if destroyed:
                self.terminal.finish(destroyed=True)
            registry = getattr(sys, "_fontlab_samples", {})
            if registry.get(KEY) is self:
                registry.pop(KEY)
            return True

        def keyPressEvent(self, event: Any) -> None:
            """Route Escape to owned Close and dispatch other keys to the native base."""
            if event.key() == core.Qt.Key_Escape:
                self.close()
                event.accept()
            else:
                gui.QDialog.keyPressEvent(self, event)

        def closeEvent(self, event: Any) -> None:
            """Delete only after owned callbacks have safely disconnected."""
            try:
                if not self.dispose():
                    event.ignore()
                    return
                gui.QDialog.closeEvent(self, event)
                self.deleteLater()
            except Exception as error:  # noqa: BLE001 - protected Qt boundary cannot leak
                self.failure(error)
                event.ignore()

    return CopyAnchors


def show_dialog() -> Any:
    """Launch through the same owned registry as existing practical Fly menus."""
    from fontlabapp import _native
    from fontlabapp.anchors.crossfont.native import Backend
    from fontlabapp.core.scripting import show_script_dialog

    qt = _native("PythonQt")
    kind = panel_type(qt.QtCore, qt.QtGui)
    return show_script_dialog(lambda parent: kind(parent, Backend()), KEY)
