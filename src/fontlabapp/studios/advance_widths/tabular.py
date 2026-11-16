# this_file: src/fontlabapp/studios/advance_widths/tabular.py
# SPDX-License-Identifier: Apache-2.0
"""Tabular tab: Tabular Width (dry run, then one Undo step) and Check Tabular Widths (read-only).

Tabular Width gives figures, figures and currency signs, or the selected
glyphs one shared advance per master (the widest in the set, or a fixed 1 to
5000 units, default 500) and centres their ink. Apply writes one
``Advance Widths: set tabular width …`` Undo step. Check compares the exact
advance of every selected layer occurrence with the first one
(``fontlabapp.metrics.tabular_width.model.capture``); it never writes.
"""

from typing import Any

from PythonQt import QtGui

from .._kerning import ERRORS
from .._kerning_ui import button, combo, get, label, row, spin
from . import widths
from ._layers import LayerPanel


class TabularPanel(LayerPanel):
    """Tabular Width and Check Tabular Widths."""

    MODES = (("tabular", "set tabular width", ("Width", "New width", "LSB", "New LSB")),)

    def build_controls(self, form: Any) -> None:
        self.group = row(self.widget, form, "Glyphs",
                         combo(self.widget, [t for t, _ in widths.SETS], self.contain(self.refresh)))
        self.width_mode = row(self.widget, form, "Width",
                              combo(self.widget, [t for t, _ in widths.WIDTH_MODES], self.contain(self.refresh)))
        self.fixed = spin(self.widget, 1, 5000, widths.FIXED_DEFAULT, suffix=" units", slot=self.contain(self.refresh))
        form.addWidget(self.fixed)
        self.fixed.setAccessibleName("Fixed width")

    def __init__(self, tool: Any) -> None:
        super().__init__(tool)
        checks = QtGui.QHBoxLayout()
        self.layout.addLayout(checks)
        label(self.widget, checks, "Check tabular widths (read-only)")
        self.check_button = button(self.widget, checks, "Check", self.contain(self.check))
        self.checked = self.table(["Glyph", "Width", "Result"])
        self.summary = label(self.widget, self.layout)
        self.report: Any = None

    def fixed_mode(self) -> bool:
        return widths.WIDTH_MODES[max(get(self.width_mode.currentIndex), 0)][1] == "fixed"

    def show_mode(self) -> None:
        super().show_mode()
        self.fixed.setEnabled(self.fixed_mode())

    def target_glyphs(self) -> list[Any]:
        names = widths.SETS[get(self.group.currentIndex)][1]
        return super().target_glyphs() if names is None else widths.find_glyphs(self.tool.package, names)

    def empty_message(self) -> str:
        if widths.SETS[get(self.group.currentIndex)][1] is not None:
            return "The font has none of these glyphs. Select your figures and use Selected glyphs."
        return super().empty_message()

    def planner(self, glyphs: list[Any], masters: list[str]) -> Any:
        mode = widths.WIDTH_MODES[get(self.width_mode.currentIndex)][1]
        return widths.tabular_planner(widths.target_widths(glyphs, masters, mode, get(self.fixed.value)))

    def hint(self) -> str:
        count = len({e.glyph.name for e in self.entries})
        return f"{count} glyph{'s' if count != 1 else ''} get one shared width and centred outlines."

    def refresh(self) -> None:
        super().refresh()
        if hasattr(self, "checked"):
            self.check()

    def check(self) -> None:
        """Check Tabular Widths: read the selected layers, compare, show; no writes."""
        self.report = None
        self.checked.set_rows([])
        try:
            report = widths.check_tabular()
        except ERRORS as error:
            self.summary.setText(str(error))
            return
        self.report = report
        self.checked.set_rows([(r.name, None, (repr(r.width), "✅ same" if r.matches else "❌ different"))
                               for r in report.rows])
        self.summary.setText(f"Tabular width checker @ {report.time}: {report.same} glyphs are on same width. "
                             f"{report.different} glyphs are on different width.")  # fmt: skip


__all__ = ["TabularPanel"]
