# this_file: src/fontlabapp/studios/kerning_batch/remove_small.py
# SPDX-License-Identifier: Apache-2.0
"""Kerning Batch Remove small tab: Scriptmix Remove Small Pairs ("Remove Small Kerning").

What: list every explicit pair whose magnitude is strictly below the
threshold (1–500, default 5 units) on the current master (default) or all
masters, ordered by magnitude then pair names (the shared
``kerning.edit.model.small_pairs`` rule, ``small_values`` over the shown snapshot); an explicit zero is listed.
Remove deletes exactly the listed pairs as one ``Kerning Batch: Remove small
kerning on <masters>`` Undo step.
Used by ``fontlabapp.studios.kerning_batch`` (tab builder).
"""

from typing import Any

from .._kerning import counts, pair_text
from .._kerning_ui import PlanPanel, get, row, spin

TITLE = "Remove Small Kerning"


def small_rows(found: dict) -> tuple[dict, list[tuple]]:
    """Deletion edits and table rows from ``{master: [(left, right, value)]}``."""
    edits = {master: {(a, b): None for a, b, _ in items} for master, items in found.items()}
    rows = [(pair_text(a, b), master, (master, v)) for master, items in found.items() for a, b, v in items]
    return edits, rows


class RemoveSmallPanel(PlanPanel):
    ACTION = "Remove"
    COLUMNS = ("Pair", "Master", "Value")

    def build_controls(self, form: Any) -> None:
        box = spin(self.widget, 1, 500, 5, prefix="|value| < ", suffix=" units", slot=self.refresh)
        self.threshold = row(self.widget, form, "Remove", box)
        self.scope = self.scope_box(form)

    def subject(self) -> str:
        return "small " + super().subject()

    def before_plan(self) -> None:
        self.fill_scope(self.scope)

    def plan(self, snapshot: Any) -> tuple[dict, list[tuple], str]:
        tool = self.tool
        masters = tool.scope(get(self.scope.currentIndex) == 1)
        found = tool.backends().edit.small_values({m: snapshot.pairs[m] for m in masters}, get(self.threshold.value))
        total = sum(len(snapshot.pairs[m]) for m in masters)
        n = len(masters)
        self.subtitle.setText(
            f"{total} pairs in {n} master{'s' if n != 1 else ''}; pairs closer to zero than the threshold are deleted."
        )
        edits, rows = small_rows(found)
        status = f"{len(rows)} to remove ({counts({m: len(f) for m, f in found.items()})})" if rows else "No pairs below the threshold"
        return edits, rows, status

    def result(self, edits: dict) -> str:
        return f"Removed {sum(len(c) for c in edits.values())} pairs ({counts({m: len(c) for m, c in edits.items()})})"


__all__ = ["TITLE", "RemoveSmallPanel", "small_rows"]
