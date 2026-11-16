# this_file: src/fontlabapp/metrics/offset/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Independent local slider drafts around complete immutable selected margins."""

import sys
from typing import Any

from fontlabapp.core.signals.scope import Scope
from fontlabapp.qt.properties import value
from fontlabapp.metrics.offset.controls import build
from fontlabapp.metrics.offset.model import preview


def panel_type(core: Any, gui: Any) -> type:
    """Bind to the supplied Qt namespace without importing Qt at module scope."""

    class SpacingOffset(gui.QWidget):
        def __init__(self, parent: Any, capture: Any, part: int) -> None:
            if part not in (2, 3):
                raise ValueError("Choose original sliders part2 or part3.")
            gui.QWidget.__init__(self, parent, core.Qt.Window | core.Qt.WindowStaysOnTopHint)
            self.part, self.capture = part, capture
            self.key = f"slider_spacing_{part}"
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
            self.last_error = str(error)
            if not self.dead and self.status is not None:
                try:
                    self.status.setText(self.last_error)
                except Exception as failure:  # noqa: BLE001 - owned Qt diagnostic boundary
                    self.last_error += "; status unavailable: " + str(failure)

        def changed(self) -> None:
            if self.closed or self.busy:
                return
            try:
                self.result = None
                if self.facts is None:
                    self.output.setPlainText(
                        "No captured selection. Refresh after selecting glyph layers."
                    )
                    return
                offset = int(value(self.groups[0][0], "value"))
                result = preview(self.facts, offset)
                lines = [
                    f"Captured geometric spacing; actual slider offset {offset:+d} units",
                    "Glyph / layer: captured L | R → candidate L | R; advance unchanged",
                ]
                for baseline, row in zip(self.facts.rows, result, strict=True):
                    name, layer, left, right, advance = row
                    if left is None:
                        lines.append(
                            f"{name} / {layer}: no geometric bounds; margins unavailable; advance {advance:g}"
                        )
                    else:
                        lines.append(
                            f"{name} / {layer}: {baseline.left:g} | {baseline.right:g} → {left:g} | {right:g}; advance {advance:g}"
                        )
                self.output.setPlainText("\n".join(lines))
                self.result = result
            except Exception as error:  # noqa: BLE001 - contain native callbacks and clear stale results
                self.result = None
                self.output.setPlainText("")
                self.failure(error)

        def refresh(self) -> None:
            if self.closed or self.busy:
                return
            self.busy = True
            try:
                facts = self.capture()
                if self.closed:
                    return
                self.facts = facts
                self.status.setText(
                    f"Captured {len(facts.rows)} selected-layer occurrences. Local preview only."
                )
                self.last_error = ""
            except Exception as error:  # noqa: BLE001 - contain native callbacks and clear stale results
                self.facts = None
                self.failure(error)
            finally:
                self.busy = False
            self.changed()

        def dispose(self, *, destroyed: bool = False) -> bool:
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
            if event.key() == core.Qt.Key_Escape:
                self.close()
                event.accept()
            else:
                gui.QWidget.keyPressEvent(self, event)

        def closeEvent(self, event: Any) -> None:
            try:
                if not self.dispose():
                    event.ignore()
                    return
                gui.QWidget.closeEvent(self, event)
                self.deleteLater()
            except Exception as error:  # noqa: BLE001 - contain native callbacks and clear stale results
                self.failure(error)
                event.ignore()

    return SpacingOffset
