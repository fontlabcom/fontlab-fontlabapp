# this_file: src/fontlabapp/studios/interpolation_doctor/tabs.py
# SPDX-License-Identifier: Apache-2.0
"""Interpolation Doctor tabs: Check, Fix, Node counts and Preview.

What: every tab reuses the Transform Studio ``Tab`` layout (glyph field,
Preview master, the result table). Check, Node counts and Preview only read
(their write-only controls are hidden); Check and Node counts also print the
four Scriptmix text reports into a read-only text box and select the flagged
glyphs in the Font window. Fix runs Make Compatible with its original
All masters default, the bases consent and the hinted-layer opt-in.
Why: ``__init__`` builds these through ``TAB_CLASSES``.
"""

from typing import Any

from PythonQt import QtCore, QtGui

from ..transform_studio.tabs import Tab, _button, _check, _combo, _get, _index, _on
from .session import Doctor, Fix, Found

CHECK_COLUMNS = ("Glyph", "Master", "Contours", "Nodes", "Anchors", "Components", "Status")
NODE_COLUMNS = ("Glyph", "Master", "Contours / nodes", "Masters")
FIX_COLUMNS = ("Glyph", "Master", "Item", "Now", "After", "Note")
PREVIEW_COLUMNS = ("Glyph", "Master", "Result")
CHECK_TITLES = ("Masters: contours, nodes, anchors, components", "Anchors", "Components")
CHECK_KINDS = ("masters", "anchors", "components")
WHAT = {"masters": "incompatible", "anchors": "mismatching", "components": "mismatching"}
WHOLE_FONT_LABEL = "Whole font"
ONLY_BAD_LABEL = "Only mismatches"
ONLY_FLAGGED_LABEL = "Show flagged glyphs only"
GHOST_LABEL = "Ghost the second master instead of the blend"
READ_ONLY_NOTE = "Read-only: nothing in the font changes."


def fix_records(fixes: list[Fix]) -> list[tuple[str, str | None, tuple[Any, ...]]]:
    out: list[tuple[str, str | None, tuple[Any, ...]]] = []
    for fix in fixes:
        if not fix.changes:
            out.append((fix.glyph, fix.master, (fix.master, "", "", "", fix.note or "no change")))
        for change in fix.changes:
            out.append((fix.glyph, fix.master, (fix.master, change.item, change.now, change.after, fix.note)))
    return out


class ReadTab(Tab):
    """A read-only tab: hides All masters, the bases consent and the hinted-layer row."""

    BASES = False
    studio: Doctor

    def __init__(self, studio: Doctor) -> None:
        super().__init__(studio)
        self.all_masters.setVisible(False)
        hints = self.layout.itemAt(self.layout.count() - 2).layout()
        for i in range(hints.count()):
            widget = hints.itemAt(i).widget()
            if widget is not None:
                widget.setVisible(False)

    def refresh(self) -> None:
        super().refresh()
        self.write_note.setText(READ_ONLY_NOTE)

    def text_box(self) -> Any:
        box = QtGui.QPlainTextEdit(self.widget)
        box.setReadOnly(True)
        box.setAccessibleName("Report")
        self.layout.addWidget(box)
        self.report_box = box
        return box

    def show_report(self, kind: str) -> str:
        text = self.studio.report(kind, self.names())
        self.report_box.setPlainText(text)
        return text

    def show_found(self, found: Found) -> Found:
        self.found = found
        self.records = found.records
        self.table.set_rows(self.records)
        return found


class CheckTab(ReadTab):
    """Masters/Anchors/Components compatibility tables plus the two text reports."""

    COLUMNS = CHECK_COLUMNS

    def controls(self) -> None:
        top = self.line()
        self.check_box = _combo(self.widget, top, "Check", list(CHECK_TITLES))
        self.check_box.currentIndexChanged.connect(lambda *args: self.check_changed())
        self.whole_font = _check(self.widget, top, WHOLE_FONT_LABEL, False)
        self.only_bad = _check(self.widget, top, ONLY_BAD_LABEL, False)
        actions = self.line()
        _button(self.widget, actions, "Check", lambda: self.guard(self.run_check))
        _button(self.widget, actions, "Select mismatches", lambda: self.guard(self.select_bad))
        _button(self.widget, actions, "Why You Not Compatible", lambda: self.guard(lambda: self.show_report("why")))
        _button(self.widget, actions, "Master Node Compatibility Report",
                lambda: self.guard(lambda: self.show_report("node")))  # fmt: skip
        self.text_box()
        self.check_changed()

    def kind(self) -> str:
        return CHECK_KINDS[max(0, _index(self.check_box))]

    def check_changed(self) -> None:
        """Set the original default scope: Masters reads the selection, the others the whole font."""
        kind = self.kind()
        self.whole_font.setChecked(kind != "masters")
        self.only_bad.setVisible(kind != "masters")
        self.only_bad.setChecked(False)

    def run_check(self) -> Found:
        whole = _on(self.whole_font)
        names = [] if whole else self.names()
        self.studio.set_glyphs(names)
        return self.show_found(self.studio.check(self.kind(), names or None, whole_font=whole,
                                                 only_bad=_on(self.only_bad)))  # fmt: skip

    def select_bad(self) -> list[str]:
        """Re-run the chosen check first, so a stale result never drives the selection."""
        found = self.run_check()
        return self.studio.select(found.flagged, WHAT[self.kind()])

    def row_chosen(self, name: str, layer: Any = None) -> None:
        """Load the row's glyph and highlight the first mismatching contour; never writes."""
        super().row_chosen(name, layer)
        found, preview = getattr(self, "found", None), self.studio.preview
        marks = found.marks.get((name, layer), ()) if found is not None else ()
        if marks and preview is not None and hasattr(preview, "highlight"):
            preview.highlight(points=marks)


class NodeTab(ReadTab):
    """Node Statistics plus Point Counter and Point Counter (Master Layers)."""

    COLUMNS = NODE_COLUMNS

    def controls(self) -> None:
        top = self.line()
        self.whole_font = _check(self.widget, top, WHOLE_FONT_LABEL, False)
        self.only_flagged = _check(self.widget, top, ONLY_FLAGGED_LABEL, False)
        actions = self.line()
        _button(self.widget, actions, "Count", lambda: self.guard(self.count))
        _button(self.widget, actions, "Select flagged", lambda: self.guard(self.select_flagged))
        _button(self.widget, actions, "Point Counter", lambda: self.guard(lambda: self.show_report("points")))
        _button(self.widget, actions, "Point Counter (Master Layers)",
                lambda: self.guard(lambda: self.show_report("master points")))  # fmt: skip
        self.text_box()

    def count(self) -> Found:
        whole = _on(self.whole_font)
        names = [] if whole else self.names()
        self.studio.set_glyphs(names)
        return self.show_found(self.studio.node_counts(names or None, whole_font=whole,
                                                       only_flagged=_on(self.only_flagged)))  # fmt: skip

    def select_flagged(self) -> list[str]:
        """Re-count first, so a stale result never drives the selection."""
        found = self.count()
        return self.studio.select(found.flagged, "flagged")


class FixTab(Tab):
    """Make Compatible: Preview (no writes) and one Undo step on the chosen glyphs."""

    COLUMNS = FIX_COLUMNS
    BASES = True  # the original panel offers "Also edit bases of automatic composites"
    studio: Doctor

    def controls(self) -> None:
        self.all_masters.setChecked(True)  # the original SCOPE = 1: all masters
        actions = self.line()
        _button(self.widget, actions, "Preview", lambda: self.guard(self.preview_fixes))
        _button(self.widget, actions, "Make compatible on chosen glyphs", lambda: self.guard(self.apply_fixes))

    def show_fixes(self, fixes: list[Fix]) -> None:
        self.records = fix_records(fixes)
        self.table.set_rows(self.records)

    def preview_fixes(self) -> list[Fix]:
        names = self.names()
        self.studio.set_glyphs(names)
        fixes = self.studio.plan_compatible(names, all_masters=self.every_master(), allow_hinted=self.hinted_allowed())
        self.show_fixes(fixes)
        edits = sum(len(fix.edits) for fix in fixes)
        self.studio.say(f"{self.app}: {edits} change(s) planned on {len(fixes)} layer(s); nothing written.")
        if names:
            self.studio.show_glyph(names[0])
        return fixes

    def apply_fixes(self) -> bool:
        names = self.names()
        self.studio.set_glyphs(names)
        done = self.studio.make_compatible(names, all_masters=self.every_master(), allow_hinted=self.hinted_allowed(),
                                           allow_bases=self.bases_allowed())  # fmt: skip
        self.show_fixes(self.studio.fixes)
        if names:
            self.studio.show_glyph(names[0])
        return done


class PreviewTab(ReadTab):
    """Interpolation Preview: a blend of two masters (or the second master) ghosted over TGlyph."""

    COLUMNS = PREVIEW_COLUMNS

    def controls(self) -> None:
        between = self.line()
        self.first = _combo(self.widget, between, "Between", [])
        self.second = _combo(self.widget, between, "and", [])
        position = self.line()
        position.addWidget(QtGui.QLabel("Position", self.widget))
        self.slider = QtGui.QSlider(self.widget)
        self.slider.setOrientation(QtCore.Qt.Horizontal)
        self.slider.setAccessibleName("Position")
        self.slider.setRange(0, 100)
        self.slider.setValue(50)
        position.addWidget(self.slider, 1)
        self.percent = QtGui.QLabel("50 %", self.widget)
        position.addWidget(self.percent)
        self.ghost_second = _check(self.widget, position, GHOST_LABEL, False)
        _button(self.widget, position, "Show blend", lambda: self.guard(self.show))
        self._masters: list[str] = []
        self.current = ""
        for signal in (self.first.currentIndexChanged, self.second.currentIndexChanged, self.slider.valueChanged):
            signal.connect(lambda *args: self.guard(self.update))
        self.ghost_second.toggled.connect(lambda *args: self.guard(self.update))

    def refresh(self) -> None:
        super().refresh()
        masters = list(self.studio.masters)
        if masters == self._masters:
            return
        self._masters = masters
        for box, index in ((self.first, 0), (self.second, len(masters) - 1)):
            box.blockSignals(True)
            box.clear()
            box.addItems(masters)
            box.setCurrentIndex(max(0, index))
            box.blockSignals(False)

    def show(self) -> Any:
        names = self.names()
        if not names:
            raise ValueError("Type glyph names or use the font selection first.")
        self.records = [(name, None, ("", "")) for name in names]
        self.table.set_rows(self.records)
        return self.blend(names[0])

    def blend(self, name: str) -> Any:
        first, second = str(_get(self.first.currentText)), str(_get(self.second.currentText))
        value = int(_get(self.slider.value))
        self.percent.setText(f"{value} %")
        self.current = name
        return self.studio.blend(name, first, second, value, ghost_second=_on(self.ghost_second))

    def update(self) -> Any:
        return self.blend(self.current) if self.current else None

    def row_chosen(self, name: str, layer: Any = None) -> None:
        if name:
            self.guard(lambda: self.blend(name))


TAB_CLASSES = [("Check", CheckTab), ("Fix", FixTab), ("Node counts", NodeTab), ("Preview", PreviewTab)]
