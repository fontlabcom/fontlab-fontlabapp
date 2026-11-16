# this_file: src/fontlabapp/metrics/worksheet/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Injected modeless worksheet owner with staged refresh and retryable Close.

All factors are local. Refresh replaces a complete immutable capture, retaining
the last report on failure. Reset restores the original profile storage types.
Window Close cancels pending input; it never commits a hidden queued editor.
"""

import sys
from typing import Any

from fontlabapp.core.signals.scope import Scope
from fontlabapp.metrics.worksheet.controls import build
from fontlabapp.metrics.worksheet.data import Snapshot, defaults, render


def panel_type(core: Any, gui: Any) -> type:
    """Bind only when opening; declarations and arithmetic remain host-free."""

    class Worksheet(gui.QWidget):
        def __init__(
            self, parent: Any, capture: Any, *, official: bool = False
        ) -> None:
            gui.QWidget.__init__(self, parent, core.Qt.Window | core.Qt.WindowStaysOnTopHint)
            self.official, self.capture = official, capture
            self.KEY = "spacing_worksheet_official" if official else "spacing_worksheet"
            self.closed = self.dead = self.busy = False
            self.snapshot, self.model, self.delegate, self.table = (
                None,
                None,
                None,
                None,
            )
            self.last_error, self.final_values = "", None
            self.scope = Scope(self.failure)
            self.terminal = Scope(self.failure)
            try:
                self.terminal.connect(
                    self.destroyed,
                    lambda *args: self.dispose(destroyed=True),
                    closing=True,
                )
                build(self, core, gui)
                self.changed()
                self.refresh()
            except BaseException:
                # Retain a visible retry owner if disconnect/setup cleanup fails.
                if self.close() is False:
                    sys.__dict__.setdefault("_fontlab_samples", {})[self.KEY] = self
                    self.show()
                raise

        def failure(self, error: Exception) -> None:
            self.last_error = str(error)
            if not self.dead and hasattr(self, "status"):
                try:
                    self.status.setText("Captured report is stale. " + self.last_error)
                except Exception:  # noqa: BLE001 - no exception leaves a Qt callback
                    self.dead = True

        def values(self) -> tuple:
            """Return the whole original model snapshot, including exact cell types."""
            return tuple(
                tuple(
                    self.model.data(self.model.index(r, c), core.Qt.EditRole)
                    for c in range(2)
                )
                for r in range(4)
            )

        def changed(self) -> None:
            if self.closed or (self.delegate is not None and self.delegate.writing):
                return
            try:
                text = render(self.snapshot, self.values())
                self.report.setPlainText(text)
            except Exception as error:  # noqa: BLE001 - model signal boundary
                self.failure(error)

        def refresh(self) -> None:
            """Commit pending acceptable input, then replace a whole stable capture."""
            if self.closed or self.busy:
                return
            self.busy = True
            try:
                if not self.delegate.finalize():
                    raise ValueError(
                        "The current editor is still closing; refresh again."
                    )
                candidate = self.capture()
                if self.closed:
                    return
                if not isinstance(candidate, Snapshot) or not candidate.rows:
                    raise ValueError(
                        "Capture did not supply a complete nonempty selection."
                    )
                text = render(candidate, self.values())
                self.report.setPlainText(text)
                self.snapshot, self.last_error = candidate, ""
                self.status.setText(
                    f"Captured {len(candidate.rows)} selected glyph-layer occurrences. Local candidates only."
                )
            except Exception as error:  # noqa: BLE001 - retain previous report/draft
                self.failure(error)
            finally:
                self.busy = False

        def reset(self) -> None:
            """Explicitly reset all factors; preserve the current captured selection."""
            if self.closed or self.busy:
                return
            self.busy = True
            try:
                self.delegate.cancel()
                before = self.values()
                blocked = self.model.blockSignals(True)
                try:
                    for row, pair in enumerate(defaults(self.official)):
                        for column, number in enumerate(pair):
                            if (
                                self.model.setData(
                                    self.model.index(row, column),
                                    number,
                                    core.Qt.EditRole,
                                )
                                is False
                            ):
                                raise RuntimeError("Qt refused Reset Factors.")
                except Exception:
                    for row, pair in enumerate(before):
                        for column, number in enumerate(pair):
                            if (
                                self.model.setData(
                                    self.model.index(row, column),
                                    number,
                                    core.Qt.EditRole,
                                )
                                is False
                            ):
                                raise RuntimeError(
                                    "Local factor rollback failed; close this worksheet."
                                )
                    raise
                finally:
                    self.model.blockSignals(blocked)
                self.last_error = ""
                self.status.setText(
                    "Factors reset. The captured selection is unchanged."
                )
            except Exception as error:  # noqa: BLE001 - local model failure boundary
                self.failure(error)
            finally:
                self.busy = False
            self.changed()

        def dispose(self, *, destroyed: bool = False) -> bool:
            """Fence late commits before signal cleanup; keep failed links for retry."""
            self.closed, self.dead, self.capture = True, destroyed, None
            if destroyed:
                if self.delegate is not None:
                    self.delegate.finish(destroyed=True)
                self.scope.finish(destroyed=True)
                self.terminal.finish(destroyed=True)
            else:
                if self.delegate is not None:
                    self.delegate.cancel()
                    if not self.delegate.finish():
                        return False
                if self.model is not None:
                    self.final_values = self.values()
                if not self.scope.finish():
                    return False
                if self.table is not None:
                    self.table.setModel(None)
                # Keep the destruction tombstone until native deletion really
                # finishes. It releases failed/never-connected editor owners
                # without dereferencing dead wrappers, including setup faults.
            windows = getattr(sys, "_fontlab_samples", {})
            if windows.get(self.KEY) is self:
                windows.pop(self.KEY)
            return True

        def closeEvent(self, event: Any) -> None:
            try:
                if not self.dispose():
                    event.ignore()
                    return
                gui.QWidget.closeEvent(self, event)
                self.deleteLater()
            except Exception as error:  # noqa: BLE001 - native close virtual boundary
                self.failure(error)
                event.ignore()

    return Worksheet
