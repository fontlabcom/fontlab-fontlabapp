# this_file: src/fontlabapp/studios/outline_doctor/tabs.py
# SPDX-License-Identifier: Apache-2.0
"""Outline Doctor tabs: Scan plus one fix tab each for Handles, Points, Segments and Overlaps.

What: every tab reuses the Transform Studio ``Tab`` layout (glyph field,
Preview master, All masters, the hinted-layer opt-in and the result table)
and adds a check chooser with that check's own options. Scan runs any check
read-only (reports can cover the whole font); fix tabs offer Preview (ghost,
no writes) and Apply (one Undo step). Choosing a check sets its default
master scope; structural fixes also show Keep masters compatible.
Why: ``__init__`` builds these through ``TAB_CLASSES``.
"""

from collections.abc import Sequence
from typing import Any

from ..transform_studio.tabs import Tab, _button, _check, _combo, _dspin, _index, _number, _on
from .checks import TABS, in_tab
from .model import Check
from .session import Row

COLUMNS = ("Glyph", "Master", "Item", "Now", "After", "Note")
COMPATIBLE_LABEL = "Keep masters compatible"
WHOLE_FONT_LABEL = "Whole font"


def records(rows: Sequence[Row]) -> list[tuple[str, str, tuple[str, ...]]]:
    """Table rows: one per issue, or one per layer without issues."""
    out = []
    for row in rows:
        if not row.issues:
            out.append((row.glyph, row.master, (row.master, "", "", "", row.note or "no change")))
        for issue in row.issues:
            note = (issue.problem if issue.problem != "gap" else "") or row.note
            out.append((row.glyph, row.master, (row.master, issue.name, issue.old, issue.new, note)))
    return out


class CheckTab(Tab):
    """A tab with a check chooser; subclasses set ``TAB``."""

    TAB = ""
    COLUMNS = COLUMNS
    BASES = True  # the tick shows only for checks whose original offered it

    def controls(self) -> None:
        self.checks: tuple[Check, ...] = in_tab(self.TAB)
        self.inputs: dict[str, dict[str, Any]] = {}
        self.option_rows: dict[str, Any] = {}
        top = self.line()
        self.check_box = _combo(self.widget, top, "Check", [c.title for c in self.checks])
        self.check_box.currentIndexChanged.connect(lambda *args: self.check_changed())
        self.compatible = _check(self.widget, top, COMPATIBLE_LABEL, True)
        self.extra(top)
        for check in self.checks:
            row = self.line()
            self.inputs[check.key] = {option.key: self.option(row, option) for option in check.options}
            self.option_rows[check.key] = row
        self.actions(self.line())
        self.check_changed()

    def extra(self, layout: Any) -> None:
        pass

    def option(self, layout: Any, option: Any) -> Any:
        if option.kind == "tick":
            return _check(self.widget, layout, option.label, bool(option.default))
        return _dspin(self.widget, layout, option.label, (option.low, option.high), float(option.default),
                      option.decimals, option.suffix)  # fmt: skip

    def check(self) -> Check:
        return self.checks[max(0, _index(self.check_box))]

    def options(self) -> dict[str, Any]:
        check = self.check()
        values = {}
        for option in check.options:
            box = self.inputs[check.key][option.key]
            values[option.key] = _on(box) if option.kind == "tick" else _number(box)
        return values

    def check_changed(self) -> None:
        """Show the chosen check's options and set its original master scope."""
        check = self.check()
        for key, row in self.option_rows.items():
            for i in range(row.count()):
                widget = row.itemAt(i).widget()
                if widget is not None:
                    widget.setVisible(key == check.key)
        self.all_masters.setChecked(check.scope == "all")
        self.compatible.setVisible(check.structural)
        self.compatible.setChecked(True)
        self.allow_bases.setVisible(check.bases)
        self.allow_bases.setChecked(False)

    def keep_compatible(self) -> bool:
        return _on(self.compatible)

    def show_rows(self, rows: Sequence[Row]) -> None:
        self.rows = list(rows)
        self.records = records(rows)
        self.table.set_rows(self.records)

    def row_chosen(self, name: str, layer: Any = None) -> None:
        """Load the chosen row's glyph and highlight its issue (and any planned ghost); never writes."""
        super().row_chosen(name, layer)
        if name:
            self.studio.ghost(getattr(self, "rows", ()), name)


class ScanTab(CheckTab):
    """Run any check read-only; reports can cover the whole font."""

    TAB = "Scan"

    def extra(self, layout: Any) -> None:
        self.whole_font = _check(self.widget, layout, WHOLE_FONT_LABEL, False)

    def check_changed(self) -> None:
        super().check_changed()
        self.compatible.setVisible(False)
        self.whole_font.setChecked(self.check().whole_font)

    def actions(self, layout: Any) -> None:
        _button(self.widget, layout, "Scan", lambda: self.guard(self.scan))

    def scan(self) -> list[Row]:
        names = [] if _on(self.whole_font) else self.names()
        self.studio.set_glyphs(names)
        rows = self.studio.scan(self.check(), self.options(), names or None, all_masters=self.every_master(),
                                whole_font=_on(self.whole_font))  # fmt: skip
        self.show_rows(rows)
        return rows


class FixTab(CheckTab):
    """Preview (ghost, no writes) and Apply (one Undo step) for the tab's fixes."""

    def actions(self, layout: Any) -> None:
        _button(self.widget, layout, "Preview", lambda: self.guard(self.preview_fix))
        _button(self.widget, layout, "Apply to chosen glyphs", lambda: self.guard(self.apply_fix))

    def _kwargs(self) -> dict[str, Any]:
        return {"all_masters": self.every_master(), "compatible": self.keep_compatible(),
                "allow_hinted": self.hinted_allowed(), "allow_bases": self.check().bases and self.bases_allowed()}  # fmt: skip

    def preview_fix(self) -> list[Row]:
        names = self.names()
        self.studio.set_glyphs(names)
        kwargs = self._kwargs()
        kwargs.pop("allow_bases")
        rows = self.studio.plan(self.check(), self.options(), names, **kwargs)
        self.show_rows(rows)
        edits = sum(len(row.edits) for row in rows)
        self.studio.say(f"{self.app}: {edits} change(s) planned on {len(rows)} layer(s); nothing written.")
        if names:
            self.studio.show_glyph(names[0])
            self.studio.ghost(rows, names[0])
        return rows

    def apply_fix(self) -> bool:
        names = self.names()
        self.studio.set_glyphs(names)
        done = self.studio.fix(self.check(), self.options(), names, **self._kwargs())
        self.show_rows(self.studio.rows)
        if names:
            self.studio.show_glyph(names[0])
        return done


def _fix_tab(title: str) -> type:
    return type(f"{title}Tab", (FixTab,), {"TAB": title, "__doc__": f"The {title} fixes."})


TAB_CLASSES = [("Scan", ScanTab), *[(title, _fix_tab(title)) for title in TABS[1:]]]
