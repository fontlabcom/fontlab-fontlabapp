# this_file: src/fontlabapp/studios/advance_widths/table.py
# SPDX-License-Identifier: Apache-2.0
"""Table tab: Width Table, read-only.

One row per selected glyph: its advance in every master (font order) and the
progression (rising, falling, flat or ⚠ mixed). "Show only mixed
progressions" filters; "Select flagged" selects the mixed glyphs in the Font
window. Nothing is written: no history, no font edit.

As in the original, a selected glyph that no longer resolves refuses the
read ("Selected glyph source changed; reopen this tool.") instead of being
dropped, and "Select flagged" first re-reads the masters and the widths behind
the shown rows, refusing (and clearing the table) when either has changed.
"""

from typing import Any

from PythonQt import QtGui

import fontlabapp.fontui as fontui

from .._kerning import ERRORS, Tool
from .._kerning_ui import Panel, button, check, label
from . import widths
from ._layers import show_glyph

MISSING = "–"
MIXED = "⚠ mixed"
GLYPHS_CHANGED = "Selected glyph source changed; reopen this tool."
INCOMPLETE = "Results are incomplete; refresh or reopen this tool."
MASTERS_CHANGED = "Masters changed since preview; refresh this tool."
SOURCE_CHANGED = "Source changed since preview; refresh this tool."


class TablePanel(Panel):
    """Width Table."""

    def __init__(self, tool: Tool) -> None:
        super().__init__(tool)
        self.only_flagged = check(self.widget, self.layout, "Show only mixed progressions", False,
                                  self.contain(self.fill))  # fmt: skip
        self.holder = QtGui.QVBoxLayout()
        self.layout.addLayout(self.holder, 1)
        self.columns: list[str] = []
        self.grid: Any = None
        self.status = label(self.widget, self.layout)
        buttons = QtGui.QHBoxLayout()
        self.layout.addLayout(buttons)
        button(self.widget, buttons, "Refresh", tool.reload)
        self.select_button = button(self.widget, buttons, "Select flagged", lambda: self.run(self.select_flagged))
        self.rows: list[tuple] = []
        self.masters: list[str] = []
        self.names: list[str] = []
        #: ``(masters, current master)`` and ``source_values()`` behind the shown rows; None when stale.
        self.domain: tuple | None = None
        self.source: tuple | None = None
        self.make_grid()

    def make_grid(self) -> None:
        """(Re)build the table when the master columns change; GlyphTable columns are fixed."""
        columns = ["Glyph", *self.masters, "Progression"]
        if columns == self.columns:
            return
        old, self.columns = self.grid, columns
        self.grid = fontui.glyph_table(columns, self.widget)
        self.grid.row_selected.connect(lambda name, master: show_glyph(self.tool, name, master))
        self.holder.addWidget(self.tool.shell.embed(self.grid))
        if old is not None:
            self.holder.removeWidget(old.widget)
            old.close()

    def clear(self) -> None:
        self.rows, self.names, self.domain, self.source = [], [], None, None
        self.fill()

    def require_glyphs(self, names: list[str]) -> list[Any]:
        """Every glyph of ``names``; a vanished one refuses (the original never drops it)."""
        glyphs = [self.tool.package.findName(name) for name in names]
        if any(glyph is None or glyph.isNull for glyph in glyphs):
            raise ValueError(GLYPHS_CHANGED)
        return glyphs

    def live_domain(self) -> tuple:
        package = self.tool.package
        return tuple(str(m) for m in package.masters), str(package.master)

    def source_values(self) -> tuple:
        """The original's source check: raw master widths and the report of ``names``."""
        glyphs = self.require_glyphs(self.names)
        raw = tuple((glyph.name, tuple(widths.master_widths(glyph, self.masters))) for glyph in glyphs)
        rows = tuple((name, tuple(values), trend) for name, values, trend in widths.width_report(glyphs, self.masters))
        return raw, rows

    def ensure_snapshot(self) -> None:
        """The original preflight before "Select flagged"; a refusal clears the shown rows."""
        try:
            if self.source is None or self.tool.package is None:
                raise ValueError(INCOMPLETE)
            if self.live_domain() != self.domain:
                raise ValueError(MASTERS_CHANGED)
            if self.source_values() != self.source:
                raise ValueError(SOURCE_CHANGED)
            if self.live_domain() != self.domain:
                raise ValueError(MASTERS_CHANGED)
        except ERRORS:
            self.clear()
            raise

    def refresh(self) -> None:
        tool = self.tool
        self.rows, self.masters, self.names, self.domain, self.source = [], list(tool.masters), [], None, None
        self.make_grid()
        domain = None if tool.package is None else self.live_domain()
        names = [] if tool.package is None else tool.selected_names()
        glyphs = [] if tool.package is None else self.require_glyphs(names)
        count = len(glyphs)
        if tool.package is None:
            self.subtitle.setText("Open a font first.")
        elif not count:
            self.subtitle.setText("Select glyphs in the Font window, then press Refresh.")
        else:
            self.subtitle.setText(f"{count} glyph{'s' if count != 1 else ''} × {len(self.masters)} masters, "
                                  f"masters in font order: {' → '.join(self.masters)}")  # fmt: skip
        self.rows = widths.width_report(glyphs, self.masters)
        if tool.package is not None:
            self.names, self.domain = names, domain
            self.source = self.source_values()
            if self.live_domain() != domain:
                raise ValueError(MASTERS_CHANGED)
        self.fill()

    def flagged(self) -> list[str]:
        return [name for name, _, trend in self.rows if trend == "mixed"]

    def fill(self) -> None:
        only = self.only_flagged.isChecked()
        shown = [r for r in self.rows if not only or r[2] == "mixed"]
        layer = self.tool.current or None
        self.grid.set_rows([(name, layer, (*[MISSING if v is None else v for v in values],
                                           MIXED if trend == "mixed" else trend))
                            for name, values, trend in shown])  # fmt: skip
        flagged = self.flagged()
        self.status.setText(f"{len(flagged)} of {len(self.rows)} glyphs with a mixed progression")
        self.select_button.setEnabled(bool(flagged))

    def select_flagged(self) -> None:
        self.ensure_snapshot()
        count = self.tool.select(self.flagged())
        self.status.setText(f"Selected {count} glyph{'s' if count != 1 else ''} in the Font window")


__all__ = ["MISSING", "MIXED", "TablePanel"]
