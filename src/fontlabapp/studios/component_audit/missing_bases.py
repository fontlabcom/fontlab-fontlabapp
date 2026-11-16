# this_file: src/fontlabapp/studios/component_audit/missing_bases.py
# SPDX-License-Identifier: Apache-2.0
"""Missing bases tab: the Scriptmix "Missing Component Bases" (Scripts/Components/Missing Bases.py).

Checks every component on every master against the glyphs and master
layers of the font and lists each component whose base is missing: the
composite, its master, the missing base and the problem ("glyph missing",
"no <master> layer" or "component without a base name"). Rows are sorted
by missing base, as the original tree grouped them. Choosing a row shows
the composite in the TGlyph preview; Select affected glyphs selects every
listed composite in the Font window. List only: this tab has no fix
buttons (the original had none), opens no history and changes no glyph.
"""

from typing import Any

from .._kerning_ui import button
from ._shared import AuditPanel, hline, plural


class MissingBasesPanel(AuditPanel):
    CHANGED = "Missing component results changed; rescan this tool."

    def build_controls(self) -> None:
        self.grid = self.table(
            ["Composite", "Master", "Missing base", "Problem"], self.row_chosen
        )
        buttons = hline(self.layout)
        self.select_button = button(
            self.widget,
            buttons,
            "Select affected glyphs",
            self.action(self.select_affected),
        )
        self.select_button.setEnabled(False)

    def scan(self, api: Any) -> Any:
        return api.missing(self.package, api.font_glyph_names(), self.masters)

    def affected(self) -> Any:
        groups = self.result or {}
        return sorted({glyph for rows in groups.values() for (glyph, _, _) in rows})

    def clear_view(self) -> None:
        self.grid.set_rows([])
        self.select_button.setEnabled(False)

    def show_result(self) -> None:
        groups = self.result or {}
        if self.package is None:
            self.subtitle.setText("Open a font first.")
        else:
            self.subtitle.setText(
                f"Every component on all {len(self.masters)} masters checked against the glyphs and master layers of this font."
            )
        self.grid.set_rows(
            [
                (glyph, master, (master, base, reason))
                for base, rows in sorted(groups.items())
                for glyph, master, reason in rows
            ]
        )
        self.select_button.setEnabled(bool(groups))
        self.note(
            f"{plural(len(groups), 'missing base')} in {len(self.affected())} glyphs"
            if groups
            else "Every component has its base glyph"
        )

    def row_chosen(self, name: str, master: Any) -> None:
        if self.tool.preview is not None and name:
            self.tool.preview.load(name, master or None)

    def select_affected(self) -> None:
        self.tool.select(self.affected())
        self.say(f"Selected {len(self.affected())} glyphs in the Font window")


__all__ = ["MissingBasesPanel"]
