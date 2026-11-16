# this_file: src/fontlabapp/studios/kerning_browser/consolidated.py
# SPDX-License-Identifier: Apache-2.0
"""The retained group-peer and persistence audits in the WP03 Browser."""
from typing import Any

from fontlabapp.core.scripting import kerning_tool_backends
from fontlabapp.studios._kerning_ui import Panel, button, get, line_edit
from fontlabapp.studios.kerning_studio.session import Studio
from fontlabapp.studios.kerning_studio.tabs import GroupsTab


model = kerning_tool_backends().persistence


class GroupsPanel(Panel):
    """Reuse the exact Same Kerning Groups controller and its preview route."""

    def __init__(self, tool: Any) -> None:
        super().__init__(tool)
        self.studio = Studio(tool.shell, font=tool.font)
        self.studio.preview = tool.preview
        self.groups = GroupsTab(self.studio)
        self.layout.addWidget(self.groups.widget)
        button(self.widget, self.layout, "Open same-group proof for selection",
               lambda: self.run(kerning_tool_backends().group_proof.run))

    def refresh(self) -> None:
        self.studio.reload()

    def clear(self) -> None:
        self.groups.peers = {}
        self.groups.table.set_rows([])


class PersistencePanel(Panel):
    """Audit explicit values with the original complete-source stale checks."""

    def __init__(self, tool: Any) -> None:
        super().__init__(tool)
        self.scope = self.scope_box(self.layout, plain=True)
        self.search = line_edit(self.widget, placeholder="Search master, pair, value or reason",
                                slot=self.contain(self.refresh))
        self.layout.addWidget(self.search)
        self.grid = self.table(["Pair", "Master", "UPM", "Value", "Reason"], self.contain(self.row_chosen))
        self.rows = {}
        self.snapshot = None

    def clear(self) -> None:
        self.rows, self.snapshot = {}, None
        self.grid.set_rows([])

    def refresh(self) -> None:
        self.clear()
        self.fill_scope(self.scope)
        if self.tool.package is None:
            return
        snapshot = model.capture(self.tool.package)
        rows = model.report(snapshot, all_masters=get(self.scope.currentIndex) == 1)
        query = get(self.search.text).strip().casefold()
        shown = [r for r in rows if query in " ".join(str(v) for v in
                 (r.master, r.upm, r.left, r.right, r.value, r.reason)).casefold()]
        model.ensure_snapshot(self.tool.package, snapshot)
        self.snapshot = snapshot
        self.rows = {(f"{r.left}  {r.right}", r.master): r for r in shown}
        self.grid.set_rows([(key[0], r.master, (r.master, r.upm, r.value, r.reason))
                            for key, r in self.rows.items()])
        self.subtitle.setText(f"{len(rows)} explicit pairs; {sum(r.at_risk for r in rows)} at risk; "
                              f"{len(shown)} shown. The measured VFJ range is not a complete persistence guarantee.")

    def row_chosen(self, name: str, master: str) -> None:
        row = self.rows.get((name, master))
        if row is not None:
            model.ensure_snapshot(self.tool.package, self.snapshot)
            self.tool.show_pair(row.left, row.right, row.master)
