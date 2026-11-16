# this_file: src/fontlabapp/fontui/raise_ascender.py
# SPDX-License-Identifier: Apache-2.0
# Original MIT provenance and attribution remain in NOTICE and immutable Scriptmix records.
"""Raise Ascender shell tab using the original ordered capture and writer."""
from time import monotonic
from typing import Any

from PythonQt import QtGui

from fontlabapp.contours.raise_ascender.model import plan
from fontlabapp.contours.raise_ascender.native import Backend
from fontlabapp.core.edit_guards import append_note
from fontlabapp.qt.properties import value
from .lifecycle import Owned
from .table import GlyphTable


class RaiseAscender(Owned):
    """Keep repeated layer occurrences and per-occurrence Undo from the original."""

    def __init__(self, studio: Any, backend: Any = None) -> None:
        super().__init__(studio.shell.widget)
        self.studio = studio
        self._package = studio.package()
        self.backend = backend
        self.accepted = None
        help_text = QtGui.QLabel(
            "Raise own nodes strictly above the associated master’s x-height + 10. "
            "Controls move too; components stay unchanged. Each layer occurrence "
            "keeps its own Undo step. This master uses every selected occurrence; "
            "all layers uses every foreground layer of the first selected glyph.", self.widget)
        help_text.setWordWrap(True)
        self.layout.addWidget(help_text)
        self.amount = QtGui.QLineEdit("10", self.widget)
        self.amount.setAccessibleName("Raise amount")
        self.layout.addWidget(self.amount)
        self.scope = QtGui.QComboBox(self.widget)
        self.scope.setAccessibleName("Raise scope")
        self.scope.addItems(["Selected layer occurrences", "First glyph: all foreground layers"])
        self.layout.addWidget(self.scope)
        self.table = GlyphTable(["Glyph", "Layer", "Nodes", "Moved"], self.widget)
        studio.shell.embed(self.table)
        self.layout.addWidget(self.table.widget)
        self.connect(self.table.row_selected, self.row_chosen)
        discard = QtGui.QPushButton("Discard preview", self.widget)
        self.connect(discard.clicked, lambda *args: self.discard())
        self.layout.addWidget(discard)
        studio.shell.set_actions(self, refresh=self.discard, preview=self.preview,
                                 apply=self.apply, dirty=lambda: self.accepted is not None,
                                 ready=self.ready, apply_label="Raise Ascenders")

    def require_target(self) -> None:
        if self._package is None or self.studio.package() is not self._package:
            raise ValueError("The captured font is no longer current; reopen the studio.")

    def row_chosen(self, name: str, layer: str) -> None:
        try:
            self.require_target()
            if self.studio.preview is not None:
                self.studio.preview.load(name, layer)
        except (ValueError, RuntimeError) as error:
            self.studio.shell.set_status(str(error))

    def inputs(self) -> tuple[str, bool]:
        return str(value(self.amount, "text")), int(value(self.scope, "currentIndex")) == 1

    def preview(self) -> None:
        """Read and stage the exact ordered operation without writing any layer."""
        self.accepted = None
        self.require_target()
        amount, every = self.inputs()
        deadline = monotonic() + 5
        if self.backend is None:
            self.backend = Backend()
        before = self.backend.capture(every, deadline)
        steps = plan(tuple(row.source for row in before.rows), amount, deadline)
        self.table.set_rows([(row.name, str(row.layer.name),
                              (str(row.layer.name), len(step.before), step.changed))
                             for row, step in zip(before.rows, steps, strict=True)])
        self.accepted = (self.inputs(), before)
        if before.rows and self.studio.preview is not None:
            row = before.rows[0]
            self.studio.preview.load(row.name, str(row.layer.name))
        self.studio.shell.set_status(f"{sum(step.changed for step in steps)} node moves planned; nothing written.")

    def ready(self) -> bool:
        self.require_target()
        if self.accepted is None or self.inputs() != self.accepted[0]:
            return False
        return self.backend.capture(self.inputs()[1], monotonic() + 5) == self.accepted[1]

    def apply(self) -> None:
        """Use the existing writer's preflight, partial-failure and Undo policies."""
        if not self.ready():
            raise ValueError("Preview the unchanged target before applying.")
        amount, every = self.inputs()
        self.accepted = None
        disclosure = {"pending_updates": (), "pending_note": ""}
        try:
            result = self.backend.execute(amount, every, disclosure=disclosure)
        except Exception as error:
            raise RuntimeError(append_note(str(error), disclosure)) from error
        self.studio.shell.set_status(append_note(
            f"Moved {result['nodes']} nodes across {result['occurrences']} occurrences; "
            f"{result['undo_steps']} Undo steps.", disclosure))

    def discard(self) -> None:
        self.accepted = None
        self.table.set_rows([])
        self.studio.shell.set_status("Preview discarded; font unchanged by discard.")
