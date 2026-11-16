# this_file: src/fontlabapp/proof/numeric/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Own complete original spinbox worksheets and captured measurement lifetime.

Both local editor profiles stay usable without a font. Refresh replaces all
facts or clears them, and preserves authored inputs. Close/Escape/replacement
fence callbacks and drain exact owned signal pairs before native deletion.
"""

import sys
from time import monotonic
from typing import Any

from fontlabapp.core.signals.scope import Scope
from fontlabapp.proof.numeric.model import calculate
from fontlabapp.qt.properties import value
from fontlabapp.proof.numeric.controls import FORMATS, build
from fontlabapp.proof.numeric.results import render


def panel_type(core: Any, gui: Any) -> type:
    """Bind the panel to the supplied native Qt namespace, only at launch."""

    class NumericProof(gui.QWidget):
        """One owned profile with local drafts and complete detached captures."""

        def __init__(self, parent: Any, capture: Any, part: int) -> None:
            """Build against the supplied binding and capture without font writes."""
            if part not in (2, 3):
                raise ValueError("Choose original spinbox part2 or part3.")
            gui.QWidget.__init__(self, parent, core.Qt.Window | core.Qt.WindowStaysOnTopHint)
            self.part, self.capture = part, capture
            self.key = f"glyph_numeric_{part}"
            self.closed = self.dead = self.busy = False
            self.facts = self.result = self.status = None
            self.last_error = ""
            self.scope, self.terminal = Scope(self.failure), Scope(self.failure)
            try:
                self.terminal.connect(
                    self.destroyed,
                    lambda *args: self.dispose(destroyed=True),
                    closing=True,
                )
                build(self, core, gui)
                self.refresh()
            except BaseException:
                if self.close() is False:
                    sys.__dict__.setdefault("_fontlab_samples", {})[self.key] = self
                    self.show()
                raise

        def failure(self, error: Exception) -> None:
            """Contain signal/virtual errors and retain diagnostic text."""
            self.last_error = str(error)
            if not self.dead and self.status is not None:
                try:
                    self.status.setText(self.last_error)
                except Exception as failure:  # noqa: BLE001 - Qt diagnostic boundary
                    self.last_error += "; status unavailable: " + str(failure)

        def precision(self, decimals: int) -> None:
            """Let native precision round all three doubles, exactly as original."""
            for key in ("decimal", "percent", "money"):
                self.controls[key].setDecimals(decimals)
            self.changed()

        def format_changed(self, index: int) -> None:
            """Keep all formats and the part3 date-section-dependent ranges."""
            meeting = self.controls["meeting"]
            meeting.setDisplayFormat(FORMATS[self.part][index])
            if self.part == 3:
                if (
                    value(meeting, "displayedSections")
                    & gui.QDateTimeEdit.DateSections_Mask
                ):
                    meeting.setDateRange(
                        core.QDate(2004, 11, 1), core.QDate(2005, 11, 30)
                    )
                    text = "Historical instant date range: 2004-11-01 to 2005-11-30."
                else:
                    meeting.setTimeRange(core.QTime(0, 7, 20), core.QTime(21, 0))
                    text = (
                        "Instant time range: 00:07:20 to 21:00:00; hidden date remains."
                    )
            else:
                text = "Instant date range: 2020-01-01 to 2040-12-31."
            self.meeting_label.setText(text)
            self.changed()

        def changed(self) -> None:
            """Calculate complete local results; never retain a stale partial output."""
            if self.closed or self.busy or not hasattr(self, "output"):
                return
            try:
                if self.facts is None:
                    self.result = None
                    self.output.setPlainText(
                        "No captured facts. Edit local controls or refresh a font selection."
                    )
                    return
                deadline = monotonic() + 2.0
                settings = tuple(
                    value(self.controls[k], "value")
                    for k in (
                        "integer",
                        "zoom",
                        "currency",
                        "decimal",
                        "percent",
                        "money",
                    )
                )
                result = calculate(self.facts, self.part, settings)
                self.output.setPlainText(
                    render(core, self.facts, result, self.controls, deadline)
                )
                self.result, self.last_error = result, ""
            except Exception as error:  # noqa: BLE001 - owned editor boundary
                self.result = None
                self.output.setPlainText("")
                self.failure(error)

        def refresh(self) -> None:
            """Replace every captured fact or clear all, preserving local controls."""
            if self.closed or self.busy:
                return
            self.busy = True
            try:
                facts = self.capture()
                if self.closed:
                    return
                self.facts = facts
                self.status.setText(
                    f"Captured {len(facts.advances)} selected layers and {len(facts.revisions)} revision dates."
                )
            except Exception as error:  # noqa: BLE001 - capture may reject changed context
                self.facts = None
                self.failure(error)
            finally:
                self.busy = False
            self.changed()

        def dispose(self, *, destroyed: bool = False) -> bool:
            """Fence late slots before draining; failed disconnect keeps Close retry."""
            self.closed, self.dead, self.capture = True, destroyed, None
            self.facts = self.result = None
            if not self.scope.finish(destroyed=destroyed):
                return False
            if destroyed:
                self.terminal.finish(destroyed=True)
            registry = getattr(sys, "_fontlab_samples", {})
            if registry.get(self.key) is self:
                registry.pop(self.key)
            return True

        def keyPressEvent(self, event: Any) -> None:
            """Escape closes only this owned worksheet."""
            if event.key() == core.Qt.Key_Escape:
                self.close()
                event.accept()
            else:
                gui.QWidget.keyPressEvent(self, event)

        def closeEvent(self, event: Any) -> None:
            """Refuse deletion until all exact owned signal pairs are disconnected."""
            try:
                if not self.dispose():
                    event.ignore()
                    return
                gui.QWidget.closeEvent(self, event)
                self.deleteLater()
            except Exception as error:  # noqa: BLE001 - native close virtual boundary
                self.failure(error)
                event.ignore()

    return NumericProof
