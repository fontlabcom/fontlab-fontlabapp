# this_file: src/fontlabapp/studios/kerning_browser/energy.py
# SPDX-License-Identifier: MIT
"""Kerning Browser Energy tab: Scriptmix Kerning Energy Report.

What: for the glyphs selected in the Font window, on the current master,
the sum of squared effective pair values ("energy") and independent
row/column means as left/right sidebearing suggestions. Pairs resolve on a
typed snapshot; explicit zero exceptions win; ambiguous pairs are named and
kept out of totals (at most 200 details). "Use selection" re-reads the
selection; "Open report" shows the full JSON in the shared read-only report
window, as the original did. Read-only: no font edits, no history.
``side_index``, ``effective``, ``energy`` and ``analyze`` are the original bodies.
Used by ``fontlabapp.studios.kerning_browser`` (tab builder).
"""

from collections.abc import Sequence
from math import isfinite
from typing import Any

from PythonQt import QtGui

import fontlabapp.fontui as fontui

from .._kerning import ERRORS, Tool
from .._kerning_ui import Panel, button

TITLE = "Kerning Energy Report"
KEY = "kerning_energy_report"
DETAIL_LIMIT = 200


def side_index(groups: dict) -> tuple[dict, dict]:
    """Index membership by glyph and pair side once per captured master."""
    indexes: tuple[dict, dict] = ({}, {})
    for key, (members, mode) in groups.items():
        sides = {"KernLeft": (0,), "KernRight": (1,), "KernBothSide": (0, 1)}.get(
            mode, ()
        )
        for side in sides:
            for name in dict.fromkeys(members):
                indexes[side].setdefault(name, []).append(key)
    return indexes


def effective(
    left: str, right: str, pairs: dict, groups: dict, *, index: tuple | None = None
) -> float:
    """Resolve one pair; an explicit glyph pair needs no class disambiguation."""
    direct = ((left, "glyphMode"), (right, "glyphMode"))
    indexes = side_index(groups) if index is None else index
    choices = []
    for side, name in enumerate((left, right)):
        found = indexes[side].get(name, [])
        if direct not in pairs and len(found) > 1:
            raise ValueError(
                f"Ambiguous kerning classes for {name} on side {side + 1}."
            )
        choices.append([(name, "glyphMode")] + [(key, "groupMode") for key in found])
    for a in choices[0]:
        for b in choices[1]:
            if (a, b) in pairs:
                value = float(pairs[a, b])
                if not isfinite(value):
                    raise ValueError("Kerning values must be finite.")
                return value
    return 0.0


def energy(matrix: Sequence[Sequence[float]]) -> float:
    """Return the sum of squared effective values in font units squared."""
    return sum(value * value for row in matrix for value in row)


def analyze(names: list[str], pairs: dict, groups: dict) -> dict:
    """Accumulate totals without storing a square matrix; keep only bad pairs."""
    if not names:
        raise ValueError("Select glyphs in the Font window first.")
    index = side_index(groups)
    rows, columns = [0.0] * len(names), [0.0] * len(names)
    row_counts, column_counts = [0] * len(names), [0] * len(names)
    score, evaluated, kept_count, kept = 0.0, 0, 0, []
    for i, left in enumerate(names):
        for j, right in enumerate(names):
            try:
                value = effective(left, right, pairs, groups, index=index)
            except ValueError as error:
                kept_count += 1
                if len(kept) < DETAIL_LIMIT:
                    kept.append(
                        {"left": left, "right": right, "reason": f"{error} Pair kept."}
                    )
                continue
            score += value * value
            evaluated += 1
            rows[i] += value
            columns[j] += value
            row_counts[i] += 1
            column_counts[j] += 1
    return {
        "read_only": True,
        "glyphs": names,
        "energy": score,
        "evaluated_pairs": evaluated,
        "kept_pair_count": kept_count,
        "kept_pairs": kept,
        "independent_spacing_suggestions": [
            {
                "glyph": name,
                "right_sidebearing_delta": rows[i] / row_counts[i]
                if row_counts[i]
                else None,
                "left_sidebearing_delta": columns[i] / column_counts[i]
                if column_counts[i]
                else None,
                "right_sample_count": row_counts[i],
                "left_sample_count": column_counts[i],
            }
            for i, name in enumerate(names)
        ],
        "usage": "Read-only report. Test one suggestion at a time; remeasure after each spacing change.",
    }


def delta(value: float | None) -> str:
    return "–" if value is None else f"{value:+.1f}"


def report(package: Any, master: str, names: list[str]) -> dict:
    """The original ``run`` result: analyse one typed snapshot, refuse it if it went stale, add the master."""
    source = fontui.kerning_snapshot(package, typed=True)
    result = analyze(names, source.pairs[master], source.groups[master])
    from fontlabapp.core.scripting import kerning_tool_backends

    kerning_tool_backends().batch.ensure_snapshot(package, source)
    result["master"] = master
    return result


class EnergyPanel(Panel):
    def __init__(self, tool: Tool) -> None:
        super().__init__(tool)
        self.grid = self.table(["Glyph", "Right sidebearing Δ", "Left sidebearing Δ", "Right samples",
                                "Left samples"], self.row_chosen)
        buttons = QtGui.QHBoxLayout()
        self.layout.addLayout(buttons)
        button(self.widget, buttons, "Use selection", tool.reload)
        self.open_button = button(self.widget, buttons, "Open report", lambda: self.run(self.open_report))
        self.result: dict | None = None

    def refresh(self) -> None:
        tool = self.tool
        self.result = None
        rows: list[tuple] = []
        if tool.package is None:
            self.subtitle.setText("Open a font first.")
        else:
            try:
                self.result = report(tool.package, tool.current, tool.selected_names())
            except ERRORS as error:
                self.subtitle.setText(f"{TITLE}: {error}")
            else:
                r = self.result
                self.subtitle.setText(
                    f"{r['master']}: {len(r['glyphs'])} glyphs, energy {r['energy']:g} over "
                    f"{r['evaluated_pairs']} pairs; {r['kept_pair_count']} ambiguous pairs kept. Read-only."
                )
                rows = [
                    (s["glyph"], r["master"], (delta(s["right_sidebearing_delta"]), delta(s["left_sidebearing_delta"]),
                                              s["right_sample_count"], s["left_sample_count"]))
                    for s in r["independent_spacing_suggestions"]
                ]
        self.grid.set_rows(rows)
        self.open_button.setEnabled(self.result is not None)

    def row_chosen(self, name: str, master: Any) -> None:
        self.tool.show_pair(name, name, master)

    def open_report(self) -> Any:
        """Show the full report in the shared read-only JSON report window."""
        if self.result is None:
            raise ValueError("Select glyphs in the Font window first.")
        return self.tool.backends().reports.show_report(self.result, title=f"{TITLE} — Read-only", key=KEY)


__all__ = ["DETAIL_LIMIT", "KEY", "TITLE", "EnergyPanel", "analyze", "effective", "energy", "report", "side_index"]
