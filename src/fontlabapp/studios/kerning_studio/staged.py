# this_file: src/fontlabapp/studios/kerning_studio/staged.py
# SPDX-License-Identifier: Apache-2.0
"""Retain the exact pair action planners while staging writes until Apply Changes."""
from typing import Any

import fontlabapp.fontui as fontui

from .session import APP, NO_FONT, WRITE_ERRORS, Studio


class StagedStudio(Studio):
    """The consolidated shell holds one explicit native-key plan and its snapshot."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.accepted: Any = None

    def draft(self) -> tuple:
        from PythonQt import QtGui

        fields = []
        for view in self.views:
            panel = view.__self__
            fields.append((id(panel), getattr(panel, "selected", None)))
            widgets = list(vars(panel).items()) + list(getattr(panel, "grid", {}).items())
            for name, widget in widgets:
                if isinstance(widget, QtGui.QLineEdit):
                    value = widget.text
                elif isinstance(widget, QtGui.QComboBox):
                    value = widget.currentIndex
                elif isinstance(widget, QtGui.QDoubleSpinBox):
                    value = widget.value
                else:
                    continue
                fields.append((name, value() if callable(value) else value))
        return self.master, tuple(fields)

    def write(self, action: str, subject: str, plan: Any) -> bool:
        self.accepted = None
        try:
            if self.shell.package() is None or self.snapshot is None:
                raise ValueError(NO_FONT)
            edits = {m: changes for m, changes in plan().items() if changes}
            native = {m: {self.native_key(m, k): v for k, v in changes.items()} for m, changes in edits.items()}
            if not native:
                raise ValueError("Nothing to apply.")
            self.accepted = native, self.snapshot, f"{APP}: {action} {subject}", self.draft()
            self.preview_changes()
            return True
        except WRITE_ERRORS as error:
            self.say(f"{APP}: {error}")
            return False

    def preview_changes(self) -> dict:
        if self.accepted is None:
            self.say("Choose a named Stage action first. No changes made.")
            return {}
        edits, _snapshot, label, _draft = self.accepted
        rows = [f"{master}: {left} {right} → {'delete' if value is None else value}"
                for master, pairs in edits.items() for (left, right), value in pairs.items()]
        self.say(f"{label} — preview only. " + "; ".join(rows))
        return edits

    def ready(self) -> bool:
        return self.accepted is not None and self.accepted[-1] == self.draft()

    def discard(self) -> None:
        self.accepted = None
        try:
            self.reload()
        except WRITE_ERRORS as error:
            self.say(f"{APP}: {error}")

    def apply_changes(self) -> bool:
        if not self.ready():
            self.say("Controls changed or no plan accepted; choose a Stage action again.")
            return False
        edits, snapshot, label, _draft = self.accepted
        self.accepted = None
        try:
            done = bool(fontui.write_kerning(self.shell.package(), edits, label, expected=snapshot))
        except WRITE_ERRORS as error:
            self.say(f"{APP}: {error}")
            return False
        self.reload()
        return done
