# this_file: src/fontlabapp/studios/kerning_batch/clamp.py
# SPDX-License-Identifier: Apache-2.0
"""Kerning Batch Clamp tab: Scriptmix Kerning Cutoff ("Kerning Cutoff").

What: clamp every master's explicit kerning to the inclusive range -250 to
100 (``kerning.cutoff.LOWER``/``UPPER``). As in the original there are no
options and no current-master subset: all masters, glyph pairs, class pairs
and both mixed exception kinds keep their typed identities, values on a
limit stay, existing zero stays, and an absent pair is never added. The plan
is the shared ``kerning.cutoff.plan``, unchanged, on a typed snapshot. The
original ran immediately; here the table lists every clamped pair first and
Apply writes exactly that set as one ``Kerning Batch: Clamp kerning on
<masters>`` Undo step, then reports each master's count as the original
printed it.

Independent implementation of Science Gothic SG-Font-Kerning-Cutoff.py v1.1,
Vassil Kateliev and Karandash Type Foundry (2025). Its source has no declared
licence; no original body is copied.
Used by ``fontlabapp.studios.kerning_batch`` (tab builder).
"""

from typing import Any

from .._kerning import pair_text, side_name
from .._kerning_ui import PlanPanel

TITLE = "Kerning Cutoff"


def clamp_rows(snapshot: Any, edits: dict) -> list[tuple]:
    """Table rows ``(pair, master, (master, value, new value))`` for each clamped pair."""
    return [
        (pair_text(side_name(pair[0]), side_name(pair[1])), master,
         (master, snapshot.pairs[master][pair], value))
        for master, changes in edits.items()
        for pair, value in changes.items()
    ]


class ClampPanel(PlanPanel):
    ACTION = "Clamp"
    COLUMNS = ("Pair", "Master", "Value", "New value")
    TYPED = True

    def plan(self, snapshot: Any) -> tuple[dict, list[tuple], str]:
        cutoff = self.tool.backends().cutoff
        edits = cutoff.plan(snapshot.pairs)
        self.lower, self.upper = cutoff.LOWER, cutoff.UPPER
        n = len(snapshot.masters)
        self.subtitle.setText(
            f"Every explicit pair on all {n} master{'s' if n != 1 else ''} is clamped to the inclusive range "
            f"[{cutoff.LOWER}, {cutoff.UPPER}]. Zero pairs stay; absent pairs are never added."
        )
        total = self.changed_in(edits)
        status = f"{total} pairs to clamp" if total else "Nothing to clamp"
        return edits, clamp_rows(snapshot, edits), status

    @staticmethod
    def changed_in(edits: dict) -> int:
        return sum(len(changes) for changes in edits.values())

    def result(self, edits: dict) -> str:
        return " ".join(
            f"{TITLE}: {master}: {len(changes)} pairs changed; inclusive [{self.lower}, {self.upper}]."
            for master, changes in edits.items()
        )


__all__ = ["TITLE", "ClampPanel", "clamp_rows"]
