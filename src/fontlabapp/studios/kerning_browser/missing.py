# this_file: src/fontlabapp/studios/kerning_browser/missing.py
# SPDX-License-Identifier: Apache-2.0
"""Kerning Browser Missing tab: Scriptmix Missing Pairs ("Missing Kerning Pairs").

What: every Left × Right combination (glyph names, characters or ``@class``
tokens; defaults "AFLPTVWY" and "aeosuy") on one master (default the
current master) that no explicit glyph or applicable class pair covers. A
pair stored with zero counts as covered. "Copy list" copies ``left right``
lines to the clipboard. Read-only: no font edits, no history.
``parse_glyphs``, ``covered`` and ``missing`` are the original bodies.
Used by ``fontlabapp.studios.kerning_browser`` (tab builder).
"""

from typing import Any

import fontlabapp.fontui as fontui

from PythonQt import QtGui

from fontlabapp.core.scripting import kerning_class_lists as class_lists
from fontlabapp.core.scripting import kerning_pairs

from .._kerning import Tool
from .._kerning_ui import Panel, button, clipboard, combo, get, line_edit, row

TITLE = "Missing Kerning Pairs"


def parse_glyphs(text: str, package: Any, members: dict[str, list[str]]) -> list[str]:
    """Glyph names from 'names', 'characters' and '@class' tokens, unique, in order."""
    out = []
    for token in text.split():
        if token.startswith("@") and token[1:] in members:
            names = members[token[1:]]
        elif package.findName(token) is not None:
            names = [token]
        else:
            names = [
                g.name
                for g in (package.findUnicode(ord(c)) for c in token)
                if g is not None
            ]
        out += [n for n in names if n not in out]
    return out


def covered(
    pairs: dict[tuple[str, str], float],
    left_classes: dict[str, list[str]],
    right_classes: dict[str, list[str]],
    left: str,
    right: str,
) -> bool:
    """Report explicit glyph/class coverage, including pairs stored with zero.

    Class indexes contain only classes allowed on their respective pair side.
    Any explicit combination of the glyph and its applicable classes covers it.
    """
    lefts = [left, *left_classes.get(left, [])]
    rights = [right, *right_classes.get(right, [])]
    return any((a, b) in pairs for a in lefts for b in rights)


def missing(
    package: Any, master: str, lefts: list[str], rights: list[str]
) -> list[tuple[str, str]]:
    """Return uncovered left/right Cartesian-product pairs in input order.

    Read the native FontLab package on the named master without switching it.
    A glyph pair or applicable class pair, even with a zero value, covers a pair.
    """
    pairs = kerning_pairs(package, master)
    left_classes, right_classes, _ = class_lists(package, master)
    return [
        (l, r)
        for l in lefts  # noqa: E741 - original body
        for r in rights
        if not covered(pairs, left_classes, right_classes, l, r)
    ]


class MissingPanel(Panel):
    def __init__(self, tool: Tool) -> None:
        super().__init__(tool)
        self.left_text = row(self.widget, self.layout, "Left",
                             line_edit(self.widget, "AFLPTVWY", "Left glyphs: names, characters or @class", self.contain(self.show_rows)))
        self.right_text = row(self.widget, self.layout, "Right",
                              line_edit(self.widget, "aeosuy", "Right glyphs: names, characters or @class", self.contain(self.show_rows)))
        self.master = row(self.widget, self.layout, "Master", combo(self.widget, [], self.contain(self.show_rows)))
        self.grid = self.table(["Left", "Right"], self.row_chosen)
        buttons = QtGui.QHBoxLayout()
        self.layout.addLayout(buttons)
        button(self.widget, buttons, "Refresh", tool.reload)
        self.copy_button = button(self.widget, buttons, "Copy list", lambda: self.run(self.copy))
        self.lefts: list[str] = []
        self.rights: list[str] = []
        self.missing: list[tuple[str, str]] = []
        self.snapshot: Any = None

    def chosen(self) -> str:
        index = get(self.master.currentIndex)
        return self.tool.masters[index] if 0 <= index < len(self.tool.masters) else ""

    def refresh(self) -> None:
        tool = self.tool
        previous = self.chosen() if get(self.master.count) else tool.current
        self.master.blockSignals(True)
        self.master.clear()
        for name in tool.masters:
            self.master.addItem(name)
        if previous in tool.masters:
            self.master.setCurrentIndex(tool.masters.index(previous))
        self.master.blockSignals(False)
        self.show_rows()

    def show_rows(self) -> None:
        tool, master = self.tool, self.chosen()
        if tool.package is None:
            self.subtitle.setText("Open a font first.")
            self.missing = []
            self.grid.set_rows([])
            self.copy_button.setEnabled(False)
            return
        self.snapshot = fontui.kerning_snapshot(tool.package)
        _, _, members = class_lists(tool.package, master)
        self.lefts = parse_glyphs(get(self.left_text.text), tool.package, members)
        self.rights = parse_glyphs(get(self.right_text.text), tool.package, members)
        self.missing = missing(tool.package, master, self.lefts, self.rights)
        combos = len(self.lefts) * len(self.rights)
        self.subtitle.setText(
            f"{len(self.lefts)} left × {len(self.rights)} right glyphs = {combos} combinations on "
            f"{master}; listed are those no glyph or class pair covers."
        )
        self.grid.set_rows([(a, master, (b,)) for a, b in self.missing])
        share = f" ({100 * len(self.missing) // combos} %)" if combos else ""
        tool.say(f"{len(self.missing)} of {combos} combinations unkerned{share}")
        self.copy_button.setEnabled(bool(self.missing))

    def row_chosen(self, name: str, master: Any) -> None:
        """Preview the chosen row's pair (first column left side, second column right side) on its master."""
        row = self.grid.current_row()
        if row is not None:
            self.tool.show_pair(row.glyph_name, row.values[0], master)

    def clear(self) -> None:
        self.lefts, self.rights, self.missing, self.snapshot = [], [], [], None
        self.grid.set_rows([])
        self.copy_button.setEnabled(False)

    def copy(self) -> str:
        self.tool.shell.package()
        if self.snapshot is None or fontui.kerning_snapshot(self.tool.package) != self.snapshot:
            raise ValueError("Kerning results are stale; refresh before copying.")
        shown = [self.missing[self.grid.proxy.mapToSource(self.grid.proxy.index(n, 0)).row()]
                 for n in range(self.grid.proxy.rowCount())]
        text = "\n".join(f"{a} {b}" for a, b in shown)
        clipboard(text)
        self.tool.say(f"Copied {len(shown)} pairs to the clipboard")
        return text


__all__ = ["TITLE", "MissingPanel", "covered", "missing", "parse_glyphs"]
