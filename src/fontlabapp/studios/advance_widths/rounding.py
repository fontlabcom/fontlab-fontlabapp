# this_file: src/fontlabapp/studios/advance_widths/rounding.py
# SPDX-License-Identifier: Apache-2.0
"""Round & scale tab: Round Advances and Scale Advances in one dry-run tab.

Round: step 1 to 100 (default 10; Scriptmix TODO:76 adds step 1, steps 2 to
100 unchanged), Nearest/Up/Down, selected glyphs or every glyph; the advance
changes, outlines and left sidebearings stay put. Scale: 10 % to 400 %
(default 100 %) of the selected glyphs; the change is split between both
sidebearings. Apply writes one ``Advance Widths: round advances …`` or
``… scale advances …`` Undo step.
"""

from typing import Any

from .._kerning_ui import combo, get, row, spin
from . import widths
from ._layers import LayerPanel

ACTIONS = ["Round advances", "Scale advances"]


class RoundScalePanel(LayerPanel):
    """Round Advances and Scale Advances."""

    MODES = (
        ("round", "round advances", ("Width", "New width", "RSB change")),
        ("scale", "scale advances", ("Width", "New width", "Outline shift")),
    )

    def build_controls(self, form: Any) -> None:
        self.action = row(self.widget, form, "Action", combo(self.widget, ACTIONS, self.contain(self.refresh)))
        self.step = row(self.widget, form, "Step", spin(self.widget, widths.STEP_MIN, widths.STEP_MAX,
                        widths.STEP_DEFAULT, suffix=" units", slot=self.contain(self.refresh)))  # fmt: skip
        self.direction = row(self.widget, form, "Round",
                             combo(self.widget, [t for t, _ in widths.DIRECTIONS], self.contain(self.refresh)))
        self.source = row(self.widget, form, "Glyphs", combo(self.widget, widths.SOURCES, self.contain(self.refresh)))
        self.percent = row(self.widget, form, "Scale advances to", spin(self.widget, 10.0, 400.0,
                           widths.PERCENT_DEFAULT, suffix=" %", decimals=1, slot=self.contain(self.refresh)))  # fmt: skip
        self.percent.setSingleStep(1.0)

    def mode(self) -> str:
        return self.MODES[max(get(self.action.currentIndex), 0)][0] if hasattr(self, "action") else "round"

    def show_mode(self) -> None:
        super().show_mode()
        rounding = self.mode() == "round"
        for widget in (self.step, self.direction, self.source):
            widget.setEnabled(rounding)
        self.percent.setEnabled(not rounding)

    def target_glyphs(self) -> list[Any]:
        if self.mode() == "round" and get(self.source.currentIndex) == 1:
            from fontlabapp.core.scripting import names_font_glyphs

            return widths.find_glyphs(self.tool.package, [name for name, _ in names_font_glyphs()])
        return super().target_glyphs()

    def planner(self, glyphs: list[Any], masters: list[str]) -> Any:
        if self.mode() == "round":
            return widths.round_planner(get(self.step.value), widths.DIRECTIONS[get(self.direction.currentIndex)][1])
        return widths.scale_planner(get(self.percent.value))

    def hint(self) -> str:
        if self.mode() == "round":
            count = len(self.entries)
            return (f"Rounds {count} layer{'s' if count != 1 else ''} to multiples of "
                    f"{get(self.step.value)}. Outlines and left sidebearings stay put.")  # fmt: skip
        count = len({e.glyph.name for e in self.entries})
        return (f"Scales the advance of {count} glyph{'s' if count != 1 else ''} to "
                f"{get(self.percent.value):g} %. The change is split between both sidebearings.")  # fmt: skip


__all__ = ["ACTIONS", "RoundScalePanel"]
