# this_file: src/fontlabapp/qt/regexp/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Own the editable pattern laboratory, complete snapshots and modeless lifetime."""

import json
import sys
from time import monotonic
from typing import Any

from fontlabapp.core.signals.scope import Scope
from fontlabapp.qt.properties import value
from fontlabapp.qt.regexp.controls import build
from fontlabapp.qt.regexp.model import Rule, evaluate


def panel_type(core: Any, gui: Any) -> type:
    """Bind only at launch; callers supply Qt 5 and their captured-name reader."""

    class PatternLab(gui.QWidget):
        KEY = "glyph_pattern"

        def __init__(self, parent: Any, capture: Any) -> None:
            gui.QWidget.__init__(self, parent, core.Qt.Window | core.Qt.WindowStaysOnTopHint)
            self.capture, self.words, self.result = capture, (), None
            self.closed = self.dead = self.busy = False
            self.last_error, self.status = "", None
            self.scope, self.terminal = Scope(self.failure), Scope(self.failure)
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
                if self.close() is False:
                    sys.__dict__.setdefault("_fontlab_samples", {})[self.KEY] = self
                    self.show()
                raise

        def failure(self, error: Exception) -> None:
            self.last_error = str(error)
            if not self.dead and self.status is not None:
                try:
                    self.status.setText(self.last_error)
                except Exception as failure:  # noqa: BLE001 - preserve reporting diagnostics
                    self.last_error += "; status unavailable: " + str(failure)

        def configuration(self) -> tuple[Rule, str]:
            return Rule(
                value(self.pattern, "currentText"),
                value(self.syntax, "currentIndex"),
                value(self.case, "checked")
                if not callable(getattr(self.case, "isChecked", None))
                else self.case.isChecked(),
                value(self.minimal, "checked")
                if not callable(getattr(self.minimal, "isChecked", None))
                else self.minimal.isChecked(),
            ), value(self.input, "currentText")

        def publish(self, words: tuple[str, ...], deadline: float) -> None:
            rule, text = self.configuration()
            result = evaluate(core, rule, text, words, deadline=deadline)
            rendered = json.dumps(result, ensure_ascii=False, indent=2)
            if not self.closed:
                self.output.setPlainText(rendered)
                self.result, self.last_error = result, ""

        def changed(self) -> None:
            if self.closed or self.busy:
                return
            self.busy = True
            try:
                self.publish(self.words, monotonic() + 2.0)
            except Exception as error:  # noqa: BLE001 - owned editor signal boundary
                self.failure(error)
            finally:
                self.busy = False

        def choose(self, index: int) -> None:
            if self.closed:
                return
            if type(index) is not int or not 0 <= index < len(self.words):
                raise ValueError("The captured glyph choice is unavailable; refresh.")
            self.input.setEditText(self.words[index])

        def refresh(self) -> None:
            """Replace all names under one deadline; preserve both authored drafts."""
            if self.closed or self.busy:
                return
            self.busy = True
            try:
                deadline = monotonic() + 2.0
                words = self.capture(deadline=deadline)
                if self.closed:
                    return
                self.publish(words, deadline)
                self.glyphs.clear()
                self.glyphs.addItems(list(words))
                self.glyphs.setEnabled(bool(words))
                self.words = words
                self.status.setText(
                    f"Captured {len(words)} glyph names. Local pattern draft only."
                )
            except Exception as error:  # noqa: BLE001 - clear stale font choices, keep drafts
                self.words = ()
                if not self.closed:
                    self.glyphs.clear()
                    self.glyphs.setEnabled(False)
                    self.publish((), monotonic() + 2.0)
                self.failure(error)
            finally:
                self.busy = False

        def dispose(self, *, destroyed: bool = False) -> bool:
            """Fence late slots before disconnect; retain failed links for Close retry."""
            self.closed, self.dead, self.capture = True, destroyed, None
            self.words, self.result = (), None
            if not self.scope.finish(destroyed=destroyed):
                return False
            if destroyed:
                self.terminal.finish(destroyed=True)
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
            except Exception as error:  # noqa: BLE001 - owned native close virtual
                self.failure(error)
                event.ignore()

    return PatternLab
