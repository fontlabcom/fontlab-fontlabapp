# this_file: src/fontlabapp/studios/anchor_transfer/masters.py
# SPDX-License-Identifier: Apache-2.0
"""Between masters tab: Mirror Across Masters as a dry run, then one Undo step.

Copies each selected glyph's anchors from one master ("From master", the
current master by default) into the ticked masters ("To masters", every
other master by default). "Scale x by advance-width ratio" is on and "Only
add missing anchors" off, as in the original; positions round half up.
Apply writes one ``Anchor Transfer: mirror anchors <subject>`` Undo step.
"""

from typing import Any

from .._kerning_ui import CheckTable, check, combo, get, row
from . import transfer
from ._panel import AnchorPanel


class MastersPanel(AnchorPanel):
    """Mirror Across Masters."""

    ACTION = "Mirror"
    UNDO = "mirror anchors"

    def build_controls(self, form: Any) -> None:
        refresh = self.contain(self.refresh)
        self.source = row(self.widget, form, "From master", combo(self.widget, [], refresh))
        self.scale = check(self.widget, form, transfer.SCALE_LABEL, True, refresh)
        self.only_missing = check(self.widget, form, transfer.ONLY_MISSING, False, refresh)
        self.targets = CheckTable(self.widget, form, ["To masters"], refresh)
        self.filled_for: tuple = ()

    def fill_masters(self) -> None:
        """Refill the master lists only when the font's masters changed (keep the user's ticks)."""
        tool = self.tool
        key = (id(tool.package), tuple(tool.masters))
        if key == self.filled_for:
            return
        self.filled_for = key
        self.source.blockSignals(True)
        self.source.clear()
        for master in tool.masters:
            self.source.addItem(master)
        if tool.current in tool.masters:
            self.source.setCurrentIndex(tool.masters.index(tool.current))
        self.source.blockSignals(False)
        self.targets.set_rows([(m,) for m in tool.masters], [m != tool.current for m in tool.masters])

    def source_master(self) -> str:
        return str(get(self.source.currentText))

    def masters(self) -> list[str]:
        ticked = [self.tool.masters[n] for n in self.targets.ticked() if n < len(self.tool.masters)]
        return transfer.mirror_targets(self.tool.masters, ticked, self.source_master())

    def plan(self) -> transfer.Dry | None:
        if self.tool.package is not None:
            self.fill_masters()
        return super().plan()

    def planner(self, glyphs: list[Any], masters: list[str]) -> Any:
        return transfer.mirror_planner(self.source_master(), bool(get(self.scale.isChecked)),
                                       bool(get(self.only_missing.isChecked)))  # fmt: skip


__all__ = ["MastersPanel"]
