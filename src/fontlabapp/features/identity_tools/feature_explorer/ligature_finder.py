# this_file: src/fontlabapp/features/identity_tools/feature_explorer/ligature_finder.py
# SPDX-License-Identifier: Apache-2.0
"""Find underscore-named glyphs and existing input glyphs. Name-derived recipes do not imply outline components.

What it does:
    Run with a font active. All original controls use the shared fly panel lifecycle.
    Feature data is font-wide; reopen after switching fonts or changing source.

How it works:
    Split underscore names into input recipes and check that every input glyph
    exists and has a safe name. Produce liga text only for usable recipes.

Why this design:
    An underscore name suggests a ligature recipe but does not prove component
    structure or existing shaping behaviour.

How to use:
    Run Features > Ligature Finder. Filter the rows, inspect missing inputs
    and copy the usable rules for review. Add and compile them separately if
    they suit the font.

Benefit:
    Find naming-based ligature candidates without silently adding
    substitutions or modifying outlines.
"""

from collections.abc import Iterable
from typing import Any
import fontlabapp as ap
from fontlabapp.features.identity_tools.table import fill
from fontlabapp.core.scripting import (
    features_dialog_type,
    show_script_dialog,
)
from fontlabapp.features.code import safe_name


qt = ap._native("PythonQt")

fontlab = ap._native("fontlab")
QtCore, QtGui = (qt.QtCore, qt.QtGui)
FeaturesDialog = features_dialog_type()


TITLE = "Ligature Recipe Finder"
KEY = "features_ligature_finder"
SUBTITLE = "Find underscore-named glyphs and existing input glyphs. Name-derived recipes do not imply outline components."
ACTION = "Copy liga snippet"


def run(names: Iterable[str]) -> list[tuple[str, str, str]]:
    """Return (ligature, space-separated inputs, status) rows in name order.

    Split the stem at underscores and apply the ligature suffix to every input.
    Ready requires safe names and every input to exist in the supplied glyph
    names. Other rows report missing/invalid inputs; underscore-only or leading
    dot names do not imply a recipe. Recipes are naming hints, not evidence of
    outline components or successful shaping. Duplicate names collapse.
    """
    known = set(names)
    rows = []
    for name in sorted(known):
        if "_" not in name or name.startswith("."):
            continue
        stem, separator, suffix = name.partition(".")
        parts = [
            part + (separator + suffix if separator else "") for part in stem.split("_")
        ]
        missing = [part for part in parts if not part or part not in known]
        valid = (
            not missing and safe_name(name) and all(safe_name(part) for part in parts)
        )
        rows.append(
            (
                name,
                " ".join(parts),
                "Ready"
                if valid
                else "Missing / invalid input: "
                + ", ".join(p or "(empty)" for p in missing),
            )
        )
    return rows


def liga_text(rows: list[tuple[str, str, str]]) -> str:
    """Build liga rules for recipes whose input glyphs all exist."""
    rules = [
        "    sub " + inputs + " by " + name + ";"
        for name, inputs, state in rows
        if state == "Ready"
    ]
    return "feature liga {\n" + "\n".join(rules) + "\n} liga;" if rules else ""


class Dialog(FeaturesDialog):
    fill = fill

    def __init__(self, parent: Any = None) -> None:
        """Initialize this owned tool and preserve its original controls."""
        super().__init__(parent, title=TITLE, subtitle=SUBTITLE, key=KEY)

    def setup(self) -> None:
        """Build the original controls inside the shared owned panel."""
        root = self.prepare()
        self.apply_button.setText(ACTION)
        self.search = QtGui.QLineEdit()
        self.search.setPlaceholderText("Filter ligature names or input glyphs…")
        root.addWidget(self.search)
        self.table = self.make_table(
            ["Ligature glyph", "Input glyphs", "Recipe status"]
        )
        root.addWidget(self.table, 1)
        self.code = QtGui.QPlainTextEdit()
        self.code.setReadOnly(True)
        root.addWidget(self.code, 1)
        self.all_rows = run(self.names)
        self._connect(self.search.textChanged, lambda *a: self.refresh())

    def refresh(self) -> None:
        """Rebuild the complete visible preview; invalidate it on failure."""
        self._preview_valid = False
        self.apply_button.setEnabled(False)
        if self.package is not None:
            self.ensure_font()
        needle = self.search.text.lower()
        self.fill([row for row in self.all_rows if needle in " ".join(row).lower()])
        self.snippet = liga_text(self.rows)
        self.code.setPlainText(
            self.snippet or "No usable underscore recipes in this view."
        )
        self.apply_button.setEnabled(bool(self.snippet))
        self.status.setText(
            f"{len(self.rows)} candidates · {sum(row[2] == 'Ready' for row in self.rows)} usable recipes"
        )
        self._preview_valid = True

    def reload(self) -> None:
        """Reread candidates from the captured font before filtering."""
        self.ensure_font()
        self.names = sorted(g.name for g in fontlab.CurrentFont().glyphs)
        self.all_rows = run(self.names)
        self.refresh()

    def proof_text(self) -> str:
        """Compare valid component sequences and their ligature glyphs."""
        return "".join("/" + name for glyph, inputs, state in self.rows
                       if state == "Ready" for name in [*inputs.split(), glyph])

    def apply(self) -> None:
        """Perform the selected original tool action on its valid preview."""
        self.ensure_preview()
        if self.snippet:
            self.copy_text(self.snippet)


def main() -> Any:
    """Replace this tool through the shared owned-window registry."""
    return show_script_dialog(Dialog, KEY)


