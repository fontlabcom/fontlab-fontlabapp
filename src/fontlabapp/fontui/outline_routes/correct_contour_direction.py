# this_file: src/fontlabapp/fontui/outline_routes/correct_contour_direction.py
# SPDX-License-Identifier: Apache-2.0
"""Set the contour direction of the selected glyphs: outer and inner contours.

What: For each selected glyph and master, the table lists every closed
contour that runs the wrong way, with its current direction. Correct
reverses them.

How: Native flContour.clockwise gives the direction; contains tests all
segment start and mid points, as FontLab's own direction command does.
Nesting within the same shape decides each edit. If layer-wide nesting would
give a different answer, the contour is listed as "inside another shape,
direction left" and kept. Overlapping outer contours stay outer. Native
segments include TrueType implied on-curve points. PostScript outer contours
run counter-clockwise; TrueType uses the opposite convention. Native
flContour.reverse reverses in place.

Why: The result depends only on the shape, not on how the font was drawn, so
imports and pasted outlines get the right direction. A wrong direction makes
holes fill in some renderers and spoils overlap removal.

Use: Select glyphs. Run the script. Choose the masters. Press Correct. Press
Reload selection after you change the selection.

Benefit: Fixes many glyphs over many masters in one Undo step, and lists
each wrong contour before anything changes.

Safety: Open contours have no direction and are not counted. These shapes
are listed and kept, but count for the cross-shape safety check:

- shared outline data (an edit would change other glyphs too);
- shapes with scale, slant or rotation (a mirror in the transform turns the
  visible direction round).

After writing, a status note reports a newly introduced final off-curve with
raw Smooth (fl#8517), which FontLab may change on save. Existing conditions
are not reported as new. Check node types after VFJ reopen. A reversal
renumbers the nodes of that contour. The panel opens with All masters
chosen. When only one master has a wrong contour, check master compatibility
after the change: the other masters keep their node order.

A glyph that has an automatic layer is listed and skipped. So is a glyph
that is a base of an automatic composite, also through other composites,
unless you tick "Also edit bases of automatic composites" (FontLab then
rebuilds those composites; anchor recovery through Undo is not assured). The script
keeps the compatibility check; writes disclose queued ids and possible date
changes.
After the write, it reads every direction back. If FontLab fails part-way,
the error says that native changes may remain. The change is recorded as one
Undo step. The one-step write, the automatic-layer rule, the pending-update
check and the panel are shared (fly.ap.contours.writer,
fly.ap.contours.panel.model); the planner belongs to this script.

Source: the author's own FontLab sample outlines_correct_direction.py,
Apache-2.0. Adapted for the current FontLab 9 API.
"""

from typing import Any

import fontlabapp.contours.panel.model as outline_panel
import fontlabapp.contours.writer as outline_writer
import fontlabapp.core.scripting as scripting  # noqa: PLR0402 - native package lookup
from fontlabapp.fontui.outline_order import (
    ReverseEditor,
    direction_changes,
    final_smooth_points,
    wrong_contours,
)

TITLE = "Correct Contour Direction"
KEY = "outlines_correct_direction"
# Native segments handle quadratic implied on-curves as well as cubics.


class CorrectContourDirection(outline_panel.panel_type()):
    """Master scope only; one row per wrong contour."""

    TITLE, KEY, ACTION, DONE, UNIT = TITLE, KEY, "Correct", "Reversed", "contour"
    HEADERS: tuple[str, ...] = ("Glyph · master", "Contour", "Now", "After")
    SCOPE = 1  # a reversal renumbers the nodes: start with all masters

    def planner(self) -> outline_writer.Planner:
        return lambda glyph, master, layer: direction_changes(layer)

    def editor(self) -> outline_writer.Editor:
        self.risk_editor = ReverseEditor()
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
    return scripting.show_script_dialog(CorrectContourDirection, KEY)


if __name__ == "__main__":
    main()

__all__ = ['ReverseEditor', 'direction_changes', 'final_smooth_points', 'main', 'wrong_contours']
