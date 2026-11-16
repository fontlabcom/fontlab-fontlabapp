# this_file: src/fontlabapp/studios/component_audit/where_used.py
# SPDX-License-Identifier: Apache-2.0
"""Where used tab: the Scriptmix "Where Is It Used?" (Scripts/Components/Where Used.py).

Type a glyph name (it starts as the current glyph; the completer offers every
glyph used as a component) to list the composites that use it: composite,
masters and layer kind (``auto``, ``mixed`` or ``components``). Choosing a
row selects that composite in the Font window, as a click did in the
original, and shows it in the TGlyph preview; Select all selects every
listed composite. Read-only: only the Font window selection changes; no
history is opened and no glyph is changed.
"""

from typing import Any

from PythonQt import QtCore, QtGui

from .._kerning_ui import button, get, line_edit
from ._shared import AuditPanel, backends, hline, plural


class WhereUsedPanel(AuditPanel):
    CHANGED = "Component usage changed; reopen this tool."

    def build_controls(self) -> None:
        self.rows: list[str] = []
        self.started = False
        self.search = line_edit(
            self.widget, "", "glyph name, e.g. period", self.contain(self.show_result)
        )
        self.search.setClearButtonEnabled(True)
        self.layout.addWidget(self.search)
        self.grid = self.table(["Composite", "Masters", "Layers"], self.row_chosen)
        self.grid.filter_box.hide()  # the search box is the original filter
        buttons = hline(self.layout)
        self.select_button = button(
            self.widget, buttons, "Select all", self.action(self.select_all)
        )
        self.select_button.setEnabled(False)

    def scan(self, api: Any) -> Any:
        return api.usage_index(self.package, self.names, self.masters)

    def refresh(self) -> None:
        super().refresh()
        if self.package is not None and not self.started:
            self.started = True
            blocked = self.search.blockSignals(True)
            try:
                self.search.setText(backends().inspect.current_name())
            finally:
                self.search.blockSignals(blocked)
            self.show_result()

    def clear_view(self) -> None:
        self.rows = []
        self.grid.set_rows([])
        self.select_button.setEnabled(False)

    def show_result(self) -> None:
        index = self.result or {}
        completer = QtGui.QCompleter(sorted(index), self.widget)
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        completer.setFilterMode(QtCore.Qt.MatchContains)
        self.search.setCompleter(completer)
        name = get(self.search.text).strip()
        if self.package is None:
            self.subtitle.setText("Open a font first.")
        else:
            self.subtitle.setText(
                f"{len(index)} glyphs are used as components in this font. Click a row to select that composite in the Font window."
            )
        users = index.get(name, {})
        self.rows = [n for n in self.names if n in users]
        table = []
        for composite in self.rows:
            entries = users[composite]
            auto = sum(1 for (_, a) in entries if a)
            kind = "auto" if auto == len(entries) else "mixed" if auto else "components"
            first = entries[0][0] if entries else None
            table.append((composite, first, (", ".join(m for (m, _) in entries), kind)))
        self.grid.set_rows(table)
        self.select_button.setEnabled(bool(self.rows))
        if not name:
            self.note("Type a glyph name")
        elif self.package is not None and self.package.findName(name) is None:
            self.note(f"No glyph named “{name}”")
        else:
            self.note(f"{name} is used by {plural(len(self.rows), 'glyph')}")

    def row_chosen(self, name: str, master: Any) -> None:
        if not name:
            return
        if self.tool.preview is not None:
            self.tool.preview.load(name, master or None)
        self.action(lambda: self.pick(name))()

    # actions (selection only) -------------------------------------------------
    def pick(self, name: str) -> None:
        self.tool.select([name])
        self.say(f"Selected {name} in the Font window")

    def select_all(self) -> None:
        self.tool.select(self.rows)
        self.say(f"Selected {len(self.rows)} glyphs in the Font window")


__all__ = ["WhereUsedPanel"]
