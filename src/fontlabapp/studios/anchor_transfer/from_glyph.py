# this_file: src/fontlabapp/studios/anchor_transfer/from_glyph.py
# SPDX-License-Identifier: Apache-2.0
"""From glyph tab: Copy Anchors From Glyph as a dry run, then one Undo step.

Copies the anchors of a named source glyph into the selected glyphs, master
by master: "Add and move (keep other anchors)" or "Replace (remove anchors
the source lacks)", x scaled by the advance-width ratio (on by default;
both coordinates are rounded as the original reads them, then x becomes
``round(x * ratio)``), on the current master or all masters.
The source glyph itself and layers that one side lacks are skipped. Apply
writes one ``Anchor Transfer: copy anchors <subject>`` Undo step.
"""

from typing import Any

from .._kerning_ui import check, combo, get, line_edit, row
from . import transfer
from ._panel import AnchorPanel


class FromGlyphPanel(AnchorPanel):
    """Copy Anchors From Glyph."""

    ACTION = "Copy"
    UNDO = "copy anchors"

    def build_controls(self, form: Any) -> None:
        refresh = self.contain(self.refresh)
        self.source = row(self.widget, form, "Source glyph",
                          line_edit(self.widget, "", "source glyph name, e.g. n", refresh))
        self.mode = row(self.widget, form, "Mode", combo(self.widget, list(transfer.MODES), refresh))
        self.scale = check(self.widget, form, transfer.SCALE_LABEL, True, refresh)
        self.scope = self.scope_box(form)

    def source_name(self) -> str:
        return str(get(self.source.text)).strip()

    def source_glyph(self) -> Any:
        name = self.source_name()
        return self.tool.package.findName(name) if self.tool.package is not None and name else None

    def masters(self) -> list[str]:
        return self.tool.scope(get(self.scope.currentIndex) == 1)

    def empty_message(self) -> str:
        return "Select the glyphs to receive anchors, then press Refresh."

    def plan(self) -> transfer.Dry | None:
        self.fill_scope(self.scope)
        return super().plan()

    def planner(self, glyphs: list[Any], masters: list[str]) -> Any:
        source = self.source_glyph()
        if not self.source_name():
            raise ValueError("Type the source glyph name")
        if source is None:
            raise ValueError(f"No glyph named “{self.source_name()}”")
        return transfer.copy_planner(source, bool(get(self.scale.isChecked)), get(self.mode.currentIndex) == 1)

    def intro(self) -> str:
        count = len(self.glyphs)
        names = ", ".join(g.name for g in self.glyphs[:8]) + (" …" if count > 8 else "")
        return f"Anchors go to {count} glyph{'s' if count != 1 else ''}: {names}"

    def summary(self) -> str:
        count = self.dry.anchors
        return f"{count} anchor change{'s' if count != 1 else ''} from {self.source_name()}"


__all__ = ["FromGlyphPanel"]
