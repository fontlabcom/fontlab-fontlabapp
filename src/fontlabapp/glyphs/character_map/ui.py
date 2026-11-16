# this_file: src/fontlabapp/glyphs/character_map/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Owned reference character pickers with atomic real-font coverage refresh."""

import sys
from typing import Any

from fontlabapp.glyphs.character_map.model import coverage, proof, scalar_text
from fontlabapp.glyphs.character_map.controls import build
from fontlabapp.core.signals.scope import Scope
from fontlabapp.qt.properties import value


def panel_type(core: Any, gui: Any, part: int) -> type:
    if part not in (2, 3):
        raise ValueError("Choose character map part2 or part3.")
    base = gui.QWidget if part == 2 else gui.QMainWindow

    class CharacterMap(base):
        def __init__(self, parent: Any, capture: Any, clipboard: Any = None) -> None:
            base.__init__(self, parent, core.Qt.Window | core.Qt.WindowStaysOnTopHint)
            self.part, self.capture, self.clipboard = part, capture, clipboard
            self.key = f"character_map_{part}"
            self.closed = self.dead = self.busy = False
            self.facts = self.status = None
            self.assignments, self.last_error = {}, ""
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
            self.last_error = str(error)
            if not self.dead and self.status is not None:
                try:
                    self.status.setText(self.last_error)
                except Exception as failure:  # noqa: BLE001 - reporting cannot escape native callbacks
                    self.last_error += "; status unavailable: " + str(failure)

        def changed(self) -> None:
            if self.closed:
                return
            if self.facts is None:
                self.output.setPlainText(
                    "FontLab coverage unavailable. Reference-font selection remains available."
                )
                return
            lines = [
                (
                    f"FontLab font #{self.facts.context[1]} / {self.facts.context[2]}: "
                    f"{len(self.facts.rows)} glyphs, {len(self.assignments)} assigned code points; "
                    f"{sum(not row.unicodes for row in self.facts.rows)} unencoded glyphs."
                ),
                "Text occurrence → Unicode → FontLab glyphs (reference rendering is separate)",
            ]
            for index, code, names in proof(self.facts, value(self.text, "text")):
                detail = ", ".join(names) if names else "MISSING"
                lines.append(f"{index + 1}: U+{code:04X} → {detail}")
            self.output.setPlainText("\n".join(lines))

        def refresh(self) -> None:
            if self.closed or self.busy:
                return
            self.busy = True
            try:
                facts = self.capture()
                assignments = coverage(facts)
                if self.closed:
                    return
                self.facts, self.assignments = facts, assignments
                self.status.setText(
                    "Coverage captured from the complete current FontLab font. Grid: BMP; proof: all Unicode."
                )
                self.last_error = ""
            except Exception as error:  # noqa: BLE001 - discard all stale capture facts together
                self.facts, self.assignments = None, {}
                self.failure(error)
            finally:
                self.busy = False
            self.grid.update()
            self.changed()

        def copy(self) -> None:
            if self.closed:
                return
            text = value(self.text, "text")
            if not scalar_text(text):
                self.failure(
                    ValueError(
                        "Text contains an incomplete Unicode character. Remove it before copying."
                    )
                )
                return
            clipboard = (
                self.clipboard
                if self.clipboard is not None
                else gui.QApplication.clipboard()
            )
            clipboard.setText(text, gui.QClipboard.Clipboard)
            if part == 3:
                clipboard.setText(text, gui.QClipboard.Selection)

        def dispose(self, *, destroyed: bool = False) -> bool:
            self.closed, self.dead = True, destroyed
            self.capture = self.clipboard = self.facts = None
            self.assignments = {}
            if not self.scope.finish(destroyed=destroyed):
                return False
            if destroyed:
                self.terminal.finish(destroyed=True)
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
            except Exception as error:  # noqa: BLE001 - retain a failed cleanup for retry
                self.failure(error)
                event.ignore()

    return CharacterMap
