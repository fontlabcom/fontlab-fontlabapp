# this_file: src/fontlabapp/studios/kerning_batch/rounding.py
# SPDX-License-Identifier: Apache-2.0
"""Kerning Batch Round tab: Scriptmix Round Values ("Round Kerning"), plus the value-plan panel Scale shares.

What: snap every explicit pair on the current master (default) or all
masters to a step (2–100, default 5 units); halves round away from zero.
"Delete pairs that round to 0" (on by default) deletes them, including an
existing explicit zero; off keeps 0 as an explicit pair. The plan is the
shared ``kerning.edit.model.round_plan`` rule (``plan_values`` over the
snapshot the table shows). The table lists every
change (Pair, Master, Value, New value); Apply writes exactly that set as one
``Kerning Batch: Round kerning on <masters>`` Undo step.
Used by ``fontlabapp.studios.kerning_batch`` (tab builder).
"""

from typing import Any

from .._kerning import counts, pair_text
from .._kerning_ui import PlanPanel, check, get, row, spin

TITLE = "Round Kerning"


def value_rows(changes: dict) -> tuple[dict, list[tuple]]:
    """Edits ``{master: {pair: new or None}}`` and table rows (sorted by pair per master) from a plan."""
    edits, rows = {}, []
    for master, items in changes.items():
        edits[master] = {pair: new for pair, (_old, new) in items.items()}
        rows += [
            (pair_text(*pair), master, (master, old, "removed" if new is None else new))
            for pair, (old, new) in sorted(items.items())
        ]
    return edits, rows


def value_status(changes: dict) -> str:
    """The originals' count line: ``"3 pairs change (Regular 2 · Bold 1)"`` or ``"Nothing to change"``."""
    total = sum(len(items) for items in changes.values())
    if not total:
        return "Nothing to change"
    return f"{total} pairs change ({counts({m: len(items) for m, items in changes.items()})})"


class ValuesPanel(PlanPanel):
    """Round and Scale: parameter, zero policy, master scope, full old/new preview."""

    COLUMNS = ("Pair", "Master", "Value", "New value")
    PARAMETER = "Round to"
    ZERO = "Delete pairs that round to 0"

    def build_controls(self, form: Any) -> None:
        self.parameter = row(self.widget, form, self.PARAMETER, self.make_parameter())
        self.drop_zero = check(self.widget, form, self.ZERO, True, self.refresh)
        self.scope = self.scope_box(form)

    def make_parameter(self) -> Any:
        return spin(self.widget, 2, 100, 5, suffix=" units", slot=self.refresh)

    def value(self) -> float:
        return get(self.parameter.value)

    def explain(self) -> str:
        return f"Values snap to multiples of {self.value()}; halves round away from zero."

    SNAP = True

    def before_plan(self) -> None:
        self.fill_scope(self.scope)

    def plan(self, snapshot: Any) -> tuple[dict, list[tuple], str]:
        tool = self.tool
        masters = tool.scope(get(self.scope.currentIndex) == 1)
        pairs = {master: snapshot.pairs[master] for master in masters}
        changes = tool.backends().edit.plan_values(pairs, self.value(), bool(self.drop_zero.isChecked()), snap=self.SNAP)
        total = sum(len(snapshot.pairs[m]) for m in masters)
        n = len(masters)
        self.subtitle.setText(f"{total} pairs in {n} master{'s' if n != 1 else ''}. " + self.explain())
        edits, rows = value_rows(changes)
        return edits, rows, value_status(changes)

    def result(self, edits: dict) -> str:
        return f"Changed {self.changed_count(edits)} pairs ({counts({m: len(c) for m, c in edits.items()})})"

    @staticmethod
    def changed_count(edits: dict) -> int:
        return sum(len(changes) for changes in edits.values())


class RoundPanel(ValuesPanel):
    ACTION = "Round"


__all__ = ["TITLE", "RoundPanel", "ValuesPanel", "value_rows", "value_status"]
