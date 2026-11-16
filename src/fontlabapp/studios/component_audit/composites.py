# this_file: src/fontlabapp/studios/component_audit/composites.py
# SPDX-License-Identifier: Apache-2.0
"""Composites tab: the Scriptmix "Components Report" (Scripts/Components/Report.py).

Lists every layer with components on the current master or on all masters:
glyph, master, components, non-zero offsets and layer kind (``auto``,
``mixed`` or ``components``), with the original filter, scope, Copy CSV and
double-click-to-open. Choosing a row shows that glyph's layer in the TGlyph
preview. Read-only: Copy CSV writes the clipboard; double-click makes the
glyph current (``activateGlyph`` and ``UpdateAll``, as the original). No
history is opened and no glyph is changed.
"""

from typing import Any

from .._kerning_ui import button, clipboard, combo, get, line_edit
from ._shared import AuditPanel, backends, hline

FILTER = "Filter by glyph, component or “auto”"


class CompositesPanel(AuditPanel):
    CHANGED = "Component report changed; reopen this tool."

    def build_controls(self) -> None:
        columns = list(backends().inspect.COLUMNS)
        self.rows: list[tuple] = []
        self.filter = line_edit(self.widget, "", FILTER, self.contain(self.show_result))
        self.filter.setClearButtonEnabled(True)
        self.scope = combo(
            self.widget,
            ["Current master", "All masters"],
            self.contain(self.show_result),
        )
        bar = hline(self.layout)
        bar.addWidget(self.filter, 1)
        bar.addWidget(self.scope)
        self.grid = self.table(columns, self.row_chosen)
        self.grid.filter_box.hide()  # the original filter (scope + "auto") replaces it
        self.grid.connect(
            self.grid.view.doubleClicked, lambda *args: self.open_current()
        )
        buttons = hline(self.layout)
        self.copy_button = button(
            self.widget, buttons, "Copy CSV", self.action(self.copy_csv)
        )
        self.copy_button.setEnabled(False)

    # original calculations ----------------------------------------------------
    def matches(self, values: Any) -> Any:
        """The original filter: current-master scope, then a substring in any column."""
        needle = get(self.filter.text).strip().lower()
        if get(self.scope.currentIndex) == 0 and values[1] != self.current_master:
            return False
        return not needle or any(needle in str(v).lower() for v in values)

    def visible_rows(self) -> Any:
        return [values for values in self.rows if self.matches(values)]

    def scan(self, api: Any) -> Any:
        return api.report(self.package, self.names, self.masters)

    # view ---------------------------------------------------------------------
    def clear_view(self) -> None:
        self.rows = []
        self.grid.set_rows([])
        self.copy_button.setEnabled(False)

    def show_result(self) -> None:
        self.rows = list(self.result or [])
        self.scope.blockSignals(True)
        self.scope.setItemText(0, f"Current master ({self.current_master})")
        self.scope.setItemText(1, f"All masters ({len(self.masters)})")
        self.scope.blockSignals(False)
        if self.package is None:
            self.subtitle.setText("Open a font first.")
        else:
            glyphs = len({r[0] for r in self.rows})
            auto = sum(1 for r in self.rows if r[4] == "auto")
            self.subtitle.setText(
                f"{glyphs} composite glyphs · {len(self.rows)} layers with components, {auto} of them auto layers. Double-click a row to open the glyph."
            )
        shown = self.visible_rows()
        self.grid.set_rows([(v[0], v[1], tuple(v[1:])) for v in shown])
        self.copy_button.setEnabled(bool(shown))
        self.note(f"{len(shown)} of {len(self.rows)} rows shown")

    def row_chosen(self, name: str, master: Any) -> None:
        if self.tool.preview is not None and name:
            self.tool.preview.load(name, master or None)

    # actions (read-only) ------------------------------------------------------
    def copy_csv(self) -> None:
        rows = self.visible_rows()
        clipboard(backends().inspect.to_csv(rows))
        self.say(f"Copied {len(rows)} rows as CSV")

    def open_current(self) -> None:
        current = self.grid.current_row()
        if current is not None:
            self.action(lambda: self.open_glyph(current.glyph_name))()

    def open_glyph(self, name: str) -> None:
        glyph = self.package.findName(name) if self.package else None
        if glyph is not None:
            self.package.activateGlyph(glyph)
            backends().update_all()


__all__ = ["FILTER", "CompositesPanel"]
