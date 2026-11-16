# this_file: src/fontlabapp/masters/background/clear/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Whole-font background removal with contained failures and owned Close."""

import sys
from typing import Any

from fontlabapp.masters.background.clear.controls import build, render
from fontlabapp.core.signals.scope import Scope
from fontlabapp.core.edit_guards import append_note


def panel_type(core: Any, gui: Any, masters: bool) -> type:
    """Inject the actual binding without importing or constructing a Qt app."""

    key = "background_clear_masters" if masters else "background_clear_all"

    class Backgrounds(gui.QDialog):
        def __init__(self, parent: Any, backend: Any) -> None:
            gui.QDialog.__init__(self, parent)
            self.setWindowFlags(self.windowFlags() | core.Qt.WindowStaysOnTopHint)
            self.backend, self.facts, self.last_result = backend, None, None
            self.masters = masters
            self.closed = self.dead = self.busy = self.completing = False
            self.last_error = ""
            self.pending_disclosure = {"pending_updates": (), "pending_note": ""}
            self.status = self.table = self.apply_button = None
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
                self.refresh()
            except BaseException:
                if self.close() is False:
                    sys.__dict__.setdefault("_fontlab_samples", {})[key] = self
                    self.show()
                raise

        def invalidate(self) -> None:
            """Drop all action targets after incomplete capture, stale input or Close."""
            self.facts = self.last_result = None
            if self.table is not None and not self.dead:
                self.table.setRowCount(0)
            if self.apply_button is not None and not self.dead:
                self.apply_button.setEnabled(False)

        def failure(self, error: Exception) -> None:
            """Failed or partial writes cannot publish success or stale targets."""
            self.last_error = f"{type(error).__name__}: {error}"
            self.invalidate()
            if self.status is not None and not self.dead:
                self.status.setText(append_note("Error: " + self.last_error, self.pending_disclosure))

        def refresh(self) -> None:
            """Explicitly reread the bound font; keep the original checkbox/scope."""
            if self.closed or self.busy:
                return
            self.busy = True
            self.pending_disclosure = {"pending_updates": (), "pending_note": ""}
            try:
                facts = self.backend.capture()
                if self.closed:
                    return
                self.facts = facts
                self.last_result, self.last_error = None, ""
                render(self, gui)
            except Exception as error:  # noqa: BLE001 - guarded native UI boundary
                self.failure(error)
            finally:
                self.busy = False

        def apply(self) -> None:
            """Run one complete current plan, then rescan only after actual success."""
            if self.closed or self.busy or self.facts is None:
                return
            self.busy = True
            self.pending_disclosure = {"pending_updates": (), "pending_note": ""}
            result = None
            try:
                result = self.backend.apply(
                    self.facts, self.masters, disclosure=self.pending_disclosure,
                )
                if self.closed:
                    return
                self.facts = self.backend.capture()
                render(self, gui)
                self.last_result, self.last_error = result, ""
                self.status.setText(append_note(
                    f"Removed {result['backgrounds']} backgrounds from {result['layers']} layers",
                    self.pending_disclosure,
                ))
            except Exception as error:  # noqa: BLE001 - retain failed/partial diagnosis
                self.failure(
                    RuntimeError(
                        f"Clear removed {result['backgrounds']} backgrounds, but the rescan failed; changes remain. Use Edit > Undo if needed. {error}"
                    )
                    if result is not None
                    else error
                )
            finally:
                self.busy = False

        def completed(self) -> None:
            """Accept/Reject/Done hide a QDialog; finish its full owned Close path."""
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
            """Fence late calls, drain exact pairs and preserve failed Close retries."""
            self.closed, self.dead, self.backend = True, destroyed, None
            self.invalidate()
            if not self.signals.finish(destroyed=destroyed):
                return False
            if destroyed:
                self.terminal.finish(destroyed=True)
            registry = getattr(sys, "_fontlab_samples", {})
            if registry.get(key) is self:
                registry.pop(key)
            return True

        def keyPressEvent(self, event: Any) -> None:
            """Escape owns the same cleanup/refusal path as the visible Close."""
            if event.key() == core.Qt.Key_Escape:
                self.close()
                event.accept()
            else:
                gui.QDialog.keyPressEvent(self, event)

        def closeEvent(self, event: Any) -> None:
            """Refuse deletion while an owned connection still needs a retry."""
            try:
                if not self.dispose():
                    event.ignore()
                    return
                gui.QDialog.closeEvent(self, event)
                self.deleteLater()
            except Exception as error:  # noqa: BLE001 - Qt close-handler boundary
                self.failure(error)
                event.ignore()

    return Backgrounds
