# this_file: src/fontlabapp/fontui/outline_routes/optimize_start_points.py
# SPDX-License-Identifier: Apache-2.0
"""Move the start node of every closed contour to its bottom-left on-curve
node.

What: For each selected glyph and master, the table lists every contour
whose start node moves, and the node that becomes the start. Optimize
applies the moves.

How: The bottom-left node is the lowest on-curve node; on a tie, the
leftmost one. "Match current master" finds it in the current master and uses
the same node number in every other master whose contour has the same node
count, so the masters stay compatible. "Bottom-left in each master" finds it
in each master on its own. FontLab's own flContour.setStartPoint turns the
node list round in place; this is meant to keep the node flags. See Safety
for VFJ reopen.

Why: A predictable start node makes masters easier to compare, helps
interpolation and keeps the order of points in exported fonts stable.

Use: Select glyphs. Run the script. Choose the rule and the masters. Press
Optimize. Press Reload selection after you change the selection.

Benefit: Sets consistent start points over many glyphs and masters in one
Undo step.

Safety: A status note reports only a newly introduced final off-curve with
raw Smooth (fl#8517), which FontLab may change on save. Check node types
after VFJ reopen. Open contours keep their start. These shapes are listed
and kept:

- shared outline data (an edit would change other glyphs too);
- shapes with scale, slant or rotation (bottom-left in stored coordinates is
  not bottom-left on screen).

A new start renumbers the nodes, so the panel opens with All masters chosen.
With "Keep masters compatible" ticked, a glyph is kept when its masters
would get different start nodes, or when other masters need the move too but
are not chosen.

A glyph that has an automatic layer is listed and skipped. So is a glyph
that is a base of an automatic composite, also through other composites,
unless you tick "Also edit bases of automatic composites" (FontLab then
rebuilds those composites; anchor recovery through Undo is not assured). The script
keeps the compatibility check; writes disclose queued ids and possible date
changes.
Every move is planned before the first one is written, so the current master
stays a valid reference. After the write, the script reads the start nodes
back. If FontLab fails part-way, the error says that native changes may
remain. The change is recorded as one Undo step. The one-step write, the
automatic-layer rule, the pending-update check and the panel are shared
(fly.ap.contours.writer, fly.ap.contours.panel.model); the planner belongs to
this
script.

Source: the author's own FontLab sample outlines_optimize_start_points.py,
Apache-2.0. Adapted for the current FontLab 9 API.
"""

from typing import Any

import PythonQt as qt

import fontlabapp.contours.panel.model as outline_panel
import fontlabapp.contours.writer as outline_writer
import fontlabapp.core.scripting as scripting  # noqa: PLR0402 - native package lookup
from fontlabapp.fontui.outline_order import (
    StartEditor,
    bottom_left,
    final_smooth_points,
    own_contours,
    start_changes,
)

QtGui = qt.QtGui
TITLE = "Optimize Start Points"
KEY = "outlines_optimize_start_points"
RULES = (
    "Match current master (keeps masters compatible)",
    "Bottom-left in each master",
)


# ---------------------------------------------------------------- start point logic


class OptimizeStartPoints(outline_panel.panel_type()):
    """Rule and master scope; one row per moved start node."""

    TITLE, KEY, ACTION, DONE, UNIT = TITLE, KEY, "Optimize", "Moved", "start node"
    HEADERS: tuple[str, ...] = ("Glyph · master", "Contour", "Start now", "New start")
    STRUCTURAL = True  # a new start renumbers the nodes

    def build_controls(self) -> None:
        self.rule = QtGui.QComboBox()
        for text in RULES:
            self.rule.addItem(text)
        self.add_row("Rule", self.rule)
        self.watch(self.rule.currentIndexChanged)

    def planner(self) -> outline_writer.Planner:
        match, current = self.rule.currentIndex == 0, self.current_master

        def plan(glyph: Any, master: str, layer: Any) -> list[outline_writer.Change]:
            reference = None
            if match and master != current:
                found = outline_writer.layer_of(glyph, current)
                reference = None if found is None or found.autoLayer else found
            return start_changes(layer, reference)

        return plan

    def editor(self) -> outline_writer.Editor:
        self.risk_editor = StartEditor()
        return self.risk_editor

    def apply(self) -> None:
        """Append save-risk advice to the result without calling it a failed
        store.
        """
        self.risk_editor = None
        super().apply()
        if self.risk_editor is not None and self.risk_editor.advice:
            note = "; ".join(self.risk_editor.advice)
            self.status.setText(f"{self.status.text} · {note}")


def main() -> Any:
    """Open the panel, or replace the one that is already open."""
    return scripting.show_script_dialog(OptimizeStartPoints, KEY)


if __name__ == "__main__":
    main()

__all__ = ['StartEditor', 'bottom_left', 'final_smooth_points', 'main', 'own_contours', 'start_changes']
