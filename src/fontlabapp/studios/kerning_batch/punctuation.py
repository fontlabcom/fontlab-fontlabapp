# this_file: src/fontlabapp/studios/kerning_batch/punctuation.py
# SPDX-License-Identifier: MIT
"""Kerning Batch Punctuation tab: Scriptmix Unbundle Punctuation Kerning.

What: turn inherited (class) values involving the selected glyphs into
explicit glyph-pair exceptions on the current master (default) or all
masters. Class definitions, class pairs and every existing explicit glyph
pair (zero included) stay. "Unicode punctuation only" (on by default)
keeps glyphs outside the Unicode P* categories; an unencoded alternate uses
its base-name glyph's code points (read from the Fontport font, never
``fgGlyph``). An ambiguous partner keeps only that pair; a master with invalid
class members is named and kept; invalid numeric data on any master keeps the
whole font (the writer validates numeric history font-wide). The table lists
every planned pair and every kept message (first 500 rows shown); Add
Exceptions writes exactly the planned pairs as one ``Kerning Batch: Add
exceptions for <n> glyphs on <masters>`` Undo step. "Use selection" re-reads the Font window
selection. ``is_punctuation``, ``expand``, ``numeric_problem``,
``master_problem`` and ``Row`` are the original bodies; only the two Fly
imports in the last two now read the same App modules through
``core.scripting.kerning_tool_backends``.

Independent behaviour rewrite after Simon Cozens, Unbundle Punctuation Kerning.py,
MIT. Repository: https://github.com/simoncozens/GlyphsScripts . No code copied.
Used by ``fontlabapp.studios.kerning_batch`` (tab builder).
"""

from dataclasses import dataclass
from math import isfinite
from typing import Any
from unicodedata import category

from fontlabapp.core.scripting import kerning_tool_backends

from .._kerning import ERRORS, Tool
from .._kerning_ui import PlanPanel, button, check, get

TITLE = "Unbundle Punctuation Kerning"
MAX_ROWS = 500
MAX_NAMES = 8


def is_punctuation(unicodes: list[int]) -> bool:
    """Use Unicode punctuation categories instead of a hard-coded name list."""
    return any(category(chr(code)).startswith("P") for code in unicodes)


def expand(
    pairs: dict, groups: dict, selected: set[str], *, kept: list | None = None
) -> dict:
    """Materialize affected effective pairs while keeping all explicit overrides."""

    def members(side: tuple) -> tuple:
        name, mode = side
        return (name,) if mode == "glyphMode" else tuple(groups[name][0])

    candidates = set()
    for a, b in pairs:
        lefts, rights = members(a), members(b)
        candidates.update(
            (left, right) for left in lefts if left in selected for right in rights
        )
        candidates.update(
            (left, right) for left in lefts for right in rights if right in selected
        )
    indexes: tuple[dict, dict] = ({}, {})
    for key, (items, mode) in groups.items():
        for side in {"KernLeft": (0,), "KernRight": (1,), "KernBothSide": (0, 1)}.get(
            mode, ()
        ):
            for name in dict.fromkeys(items):
                indexes[side].setdefault(name, []).append(key)
    changes = {}
    for left, right in sorted(candidates):
        pair = ((left, "glyphMode"), (right, "glyphMode"))
        if pair in pairs:
            continue
        choices = []
        for index, name in enumerate((left, right)):
            found = indexes[index].get(name, [])
            if len(found) > 1:
                if kept is not None:
                    kept.append(
                        (pair, f"Ambiguous kerning classes for {name}; pair kept")
                    )
                break
            choices.append(
                [(name, "glyphMode")] + [(key, "groupMode") for key in found]
            )
        if len(choices) != 2:
            continue
        resolved = [
            pairs[a, b] for a in choices[0] for b in choices[1] if (a, b) in pairs
        ]
        if resolved:
            changes[pair] = resolved[0]
    return changes


def numeric_problem(package: Any, master: str, pairs: dict) -> str:
    """Match whole-value and persistence checks without private App calls.

    Whole-unit, finite and signed32 rules use the public writer helper. The
    writer exposes no public range validator, so repeat its small range rule.
    """
    values = kerning_tool_backends().edit

    upm = package.upm
    invalid_upm = f"{master}: invalid UPM; master kept"
    if isinstance(upm, bool) or not isinstance(upm, (int, float)):
        return invalid_upm
    try:
        upm = float(upm)
    except (ValueError, OverflowError):
        return invalid_upm
    if not isfinite(upm) or upm <= 0:
        return invalid_upm
    for pair, value in pairs.items():
        label = " + ".join(
            ("@" if mode == "groupMode" else "") + name for name, mode in pair
        )
        try:
            values.whole_value(value)
            if abs(value) > 2 * upm:
                raise ValueError(f"outside +/-{2 * upm:g} (twice UPM)")
        except (ValueError, OverflowError) as error:
            return f"{master}: {label} = {value!r}: {error}; master kept"
    return ""


def master_problem(package: Any, master: str, pairs: dict, groups: dict) -> str:
    """Check the writer's value limits and every existing glyph/class pair."""
    batch = kerning_tool_backends().batch

    problem = numeric_problem(package, master, pairs)
    if problem:
        return problem
    for pair in pairs:
        try:
            batch.validate_pair(package, master, pair, groups=groups)
        except ValueError as error:
            classes = [f"@{name}" for name, mode in pair if mode == "groupMode"]
            label = "class " + ", ".join(classes) if classes else "glyph pair"
            return f"{master}: {label}: {error}; master kept"
    return ""


@dataclass(frozen=True)
class Row:
    """One explicit exception or a named kept-selection message."""

    master: str
    pair: tuple
    value: float = 0
    note: str = ""


def plural(count: int, word: str) -> str:
    """``"1 glyph"`` / ``"2 glyphs"``, as the shared selection panel wrote it."""
    return f"{count} {word}{'' if count == 1 else 's'}"


def glyph_codes(font: Any, name: str) -> list[int]:
    """Code points of ``name`` in the Fontport font, else of its base name before the first ``.``."""
    def codes(glyph_name: str) -> list[int]:
        if font is None or glyph_name not in font:
            return []
        return list(getattr(font[glyph_name], "unicodes", ()) or ())

    found = codes(name)
    if not found and "." in name:
        found = codes(name.split(".", 1)[0])
    return found


def plan_rows(package: Any, font: Any, snapshot: Any, names: list[str], masters: list[str],
              punctuation_only: bool) -> list[Row]:
    """The original ``plan_rows`` on a typed snapshot: planned exceptions and kept messages."""
    batch = kerning_tool_backends().batch
    numeric_issues = {
        master: problem
        for master, pairs in snapshot.pairs.items()
        if (problem := numeric_problem(package, master, pairs))
    }
    if numeric_issues:
        empty_pair = (("", "glyphMode"), ("", "glyphMode"))
        return [
            *(Row(master, empty_pair, note=problem) for master, problem in numeric_issues.items()),
            Row(
                "All masters",
                empty_pair,
                note="Font-wide numeric history check failed; all masters kept. Correct the named data before applying.",
            ),
        ]
    selected, rows = set(), []
    for name in names:
        glyph = package.findName(name)
        if glyph is None or glyph.isNull:
            rows.append(Row("", ((name, "glyphMode"), ("", "glyphMode")), note="missing glyph, kept"))
            continue
        if punctuation_only and not is_punctuation(glyph_codes(font, name)):
            rows.append(Row("", ((name, "glyphMode"), ("", "glyphMode")), note="outside Unicode punctuation, kept"))
        else:
            selected.add(name)
    for master in masters:
        pairs, groups = snapshot.pairs[master], snapshot.groups[master]
        problem = master_problem(package, master, pairs, groups)
        if problem:
            rows.append(Row(master, (("", "glyphMode"), ("", "glyphMode")), note=problem))
            continue
        changes = {}
        for name in sorted(selected):
            kept: list = []
            found = expand(pairs, groups, {name}, kept=kept)
            rows.extend(Row(master, pair, note=note) for pair, note in kept)
            if not found and not kept:
                rows.append(Row(master, ((name, "glyphMode"), ("", "glyphMode")),
                                note="no inherited pairs to expand, kept"))
            for pair, value in found.items():
                try:
                    batch.validate_pair(package, master, pair, groups=groups)
                except ValueError as error:
                    rows.append(Row(master, pair, note=f"{error}; pair kept"))
                    continue
                changes[pair] = value
        rows.extend(Row(master, pair, value) for pair, value in changes.items())
    return rows


def row_edits(rows: list[Row]) -> dict:
    """``{master: {typed pair: value}}`` for every row without a note (the original ``write``)."""
    edits: dict = {}
    for item in rows:
        if not item.note:
            edits.setdefault(item.master, {})[item.pair] = item.value
    return edits


class PunctuationPanel(PlanPanel):
    ACTION = "Add Exceptions"
    UNDO = "Add exceptions"
    COLUMNS = ("Master", "Left", "Right", "Value / kept")
    TYPED = True

    def __init__(self, tool: Tool) -> None:
        self.names: list[str] | None = None
        self.found: list[Row] = []
        super().__init__(tool)

    def build_controls(self, form: Any) -> None:
        self.punctuation_only = check(self.widget, form, "Unicode punctuation only", True, self.refresh)
        self.scope = self.scope_box(form, plain=True)
        button(self.widget, form, "Use selection", self.reselect)

    def reselect(self) -> None:
        """Take the Font window selection again and plan again."""
        self.names = None
        self.tool.reload()

    def subject(self) -> str:
        """``"for 2 glyphs on Regular"``: the selection and the masters the plan changes."""
        return f"for {plural(len(self.names or []), 'glyph')} on {self.changed_masters()}"

    def before_plan(self) -> None:
        self.fill_scope(self.scope)
        if self.names is None:
            try:
                self.names = self.tool.selected_names()
            except ERRORS:
                self.names = []

    def plan(self, snapshot: Any) -> tuple[dict, list[tuple], str]:
        tool, names = self.tool, self.names or []
        if not names:
            raise ValueError("Select glyphs in the Font window. Then press Use selection.")
        shown = ", ".join(names[:MAX_NAMES]) + (" …" if len(names) > MAX_NAMES else "")
        self.subtitle.setText(f"{plural(len(names), 'glyph')}: {shown}")
        masters = tool.scope(get(self.scope.currentIndex) == 1)
        found = plan_rows(tool.package, tool.font(), snapshot, names, masters, bool(self.punctuation_only.isChecked()))
        edits = row_edits(found)
        self.found = found[:MAX_ROWS]
        rows = [
            (item.master, item.master if item.master in tool.masters else None,
             (item.pair[0][0], item.pair[1][0], item.note or f"{item.value:g}"))
            for item in self.found
        ]
        ready = sum(len(changes) for changes in edits.values())
        more = f" (table shows the first {MAX_ROWS})" if len(found) > MAX_ROWS else ""
        return edits, rows, f"{plural(ready, 'row')} ready" + more

    def row_chosen(self, name: str, master: Any) -> None:
        """Preview the chosen planned pair on its master; the font-wide note row has no master."""
        row = self.grid.current_row()
        if master and row is not None:
            self.tool.show_pair(row.values[0], row.values[1], master)

    def result(self, edits: dict) -> str:
        return f"Added {sum(len(items) for items in edits.values())} exceptions. Classes kept."


__all__ = ["MAX_ROWS", "TITLE", "PunctuationPanel", "Row", "expand", "glyph_codes", "is_punctuation",
           "master_problem", "numeric_problem", "plan_rows", "row_edits"]
