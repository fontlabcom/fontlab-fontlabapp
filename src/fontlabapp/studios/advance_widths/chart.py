# this_file: src/fontlabapp/studios/advance_widths/chart.py
# SPDX-License-Identifier: Apache-2.0
"""Chart tab: Width Chart, read-only.

Masters on x (sorted by the first axis), advance width on y, one line for
each of the first 12 selected glyphs (``masters.inspect.views.LineChart``).
Nothing is written.
"""

from typing import Any

from fontlabapp.core.scripting import masters_view_types

from .._kerning import Tool
from .._kerning_ui import Panel, button, label
from . import widths

MAX_SERIES = 12


class ChartPanel(Panel):
    """Width Chart."""

    def __init__(self, tool: Tool) -> None:
        super().__init__(tool)
        self.chart = masters_view_types().LineChart(self.widget)
        self.layout.addWidget(self.chart, 1)
        self.status = label(self.widget, self.layout)
        button(self.widget, self.layout, "Refresh", tool.reload)
        self.data: dict[str, Any] = {}

    def clear(self) -> None:
        self.data = {}
        self.chart.masters, self.chart.series = [], []
        self.chart.update()
        self.status.setText("")

    def refresh(self) -> None:
        tool = self.tool
        self.clear()
        glyphs = [] if tool.package is None else widths.find_glyphs(tool.package, tool.selected_names())
        if tool.package is None:
            self.subtitle.setText("Open a font first.")
            return
        if not glyphs:
            self.subtitle.setText("Select glyphs in the Font window, then press Refresh.")
            return
        count = len(glyphs)
        self.subtitle.setText(f"{count} glyph{'s' if count != 1 else ''}")
        order = widths.master_order(tool.package)
        for glyph in glyphs[:MAX_SERIES]:
            self.data[glyph.name] = widths.master_widths(glyph, order)
        self.chart.masters = order
        self.chart.series = [(name, [w for (_, w) in row]) for (name, row) in self.data.items()]
        self.chart.update()
        note = f" · first {MAX_SERIES} glyphs shown" if count > MAX_SERIES else ""
        self.status.setText(f"Advance widths across {len(order)} masters{note}")


__all__ = ["MAX_SERIES", "ChartPanel"]
