# this_file: src/fontlabapp/studios/advance_widths/marks.py
# SPDX-License-Identifier: Apache-2.0
"""Marks tab: Zero-Width Marks as a dry run, then one Undo step.

Sets the advance of the selected combining marks to 0 and keeps the
outline, hangs it left by the old width, or centres its ink on the origin.
"Only combining marks (Mn, Me, or name ending in comb)" is on by default.
Apply writes one ``Advance Widths: zero mark widths …`` Undo step.
"""

from typing import Any

from .._kerning_ui import check, combo, get, row
from . import widths
from ._layers import LayerPanel

ONLY_MARKS = "Only combining marks (Mn, Me, or name ending in comb)"


class MarksPanel(LayerPanel):
    """Zero-Width Marks."""

    MODES = (("zero", "zero mark widths", ("Width", "New width", "Outline shift")),)

    def build_controls(self, form: Any) -> None:
        self.only_marks = check(self.widget, form, ONLY_MARKS, True, self.contain(self.refresh))
        self.placement = row(self.widget, form, "Outline",
                             combo(self.widget, [t for t, _ in widths.PLACEMENTS], self.contain(self.refresh)))

    def target_glyphs(self) -> list[Any]:
        self.names = self.tool.selected_names()
        glyphs = widths.find_glyphs(self.tool.package, self.names)
        if get(self.only_marks.isChecked):
            glyphs = [g for g in glyphs if widths.is_mark(g, widths.glyph_unicodes(self.tool.package, g))]
        return glyphs

    def empty_message(self) -> str:
        if getattr(self, "names", None) and get(self.only_marks.isChecked):
            return "The selection has no combining marks. Select marks, or clear the filter."
        return super().empty_message()

    def planner(self, glyphs: list[Any], masters: list[str]) -> Any:
        return widths.zero_planner(widths.PLACEMENTS[get(self.placement.currentIndex)][1])

    def hint(self) -> str:
        count = len({e.glyph.name for e in self.entries})
        return f"Sets the advance of {count} mark{'s' if count != 1 else ''} to 0."


__all__ = ["ONLY_MARKS", "MarksPanel"]
