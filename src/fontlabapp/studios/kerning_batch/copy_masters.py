# this_file: src/fontlabapp/studios/kerning_batch/copy_masters.py
# SPDX-License-Identifier: Apache-2.0
"""Kerning Batch Copy masters tab: Scriptmix Copy Between Masters ("Copy Kerning Between Masters").

What: copy one master's explicit pairs (From, default the current master)
to the ticked target masters, optionally scaled (0–400 %, one decimal,
default 100 %, halves away from zero), in one of three modes: Replace all
pairs (target pairs absent from the source are deleted), Add missing pairs
only, or Overwrite matching pairs, keep others. The plan is the shared
``kerning.edit.model.copy_plan``/``summary``, unchanged; explicit zero and
absence stay distinct. The confirmation is the original's: the "To masters"
table shows each target's Pairs now, Added, Changed and Removed counts, and
Copy is enabled only when a target is ticked and the plan changes something;
there is no modal box (the original had none). Copy writes exactly the
displayed plan as one ``Kerning Batch: Copy kerning from <source> to
<targets>`` Undo step.
Used by ``fontlabapp.studios.kerning_batch`` (tab builder).
"""

from typing import Any

from PythonQt import QtGui

import fontlabapp.fontui as fontui

from .._kerning import ERRORS, Tool
from .._kerning_ui import CheckTable, Panel, button, combo, get, label, row, spin

TITLE = "Copy Kerning Between Masters"
MODES = [
    ("Replace all pairs", "replace"),
    ("Add missing pairs only", "missing"),
    ("Overwrite matching pairs, keep others", "matching"),
]


def copy_edits(edit: Any, pairs: dict, source: str, targets: list[str], mode: str, percent: float) -> dict:
    """``{target: {pair: value or None}}`` for each ticked target, from one snapshot's pairs."""
    return {target: edit.copy_plan(pairs[source], pairs[target], mode, percent) for target in targets}


class CopyPanel(Panel):
    ACTION = "Copy"

    def __init__(self, tool: Tool) -> None:
        super().__init__(tool)
        form = self.layout
        self.source = row(self.widget, form, "From", combo(self.widget, [], self.rebuild))
        self.percent = row(self.widget, form, "Scale",
                           spin(self.widget, 0.0, 400.0, 100.0, suffix=" %", decimals=1, slot=self.update))
        self.mode = row(self.widget, form, "Mode", combo(self.widget, [text for text, _ in MODES], self.update))
        label(self.widget, form, "To masters")
        self.targets = CheckTable(self.widget, form, ["Master", "Pairs now", "Added", "Changed", "Removed"],
                                  self.toggled)
        self.count = label(self.widget, form)
        buttons = QtGui.QHBoxLayout()
        form.addLayout(buttons)
        button(self.widget, buttons, "Refresh", tool.reload)
        self.apply_button = button(self.widget, buttons, "Copy", self.apply)
        self.checked: dict[str, bool] = {}
        self.snapshot: Any = None
        self.edits: dict = {}
        self.filling = False

    def source_master(self) -> str:
        masters = self.tool.masters
        index = get(self.source.currentIndex)
        return masters[index] if masters and 0 <= index < len(masters) else ""

    def mode_key(self) -> str:
        return MODES[get(self.mode.currentIndex)][1]

    def chosen_targets(self) -> list[str]:
        return [m for m in self.tool.masters if self.checked.get(m) and m != self.source_master()]

    def set_targets(self, names: list[str]) -> None:
        """Tick exactly these target masters (used by scripts and tests)."""
        self.checked = {m: m in names for m in self.tool.masters}
        self.rebuild()

    def toggled(self) -> None:
        if self.filling:
            return
        ticked = set(self.targets.ticked())
        for number in range(get(self.targets.view.rowCount)):
            self.checked[self.targets.text(number, 0)] = number in ticked
        self.update()

    def refresh(self) -> None:
        """After a reload: refill the source masters (current master first chosen), then the targets."""
        tool = self.tool
        self.filling = True
        previous = self.source_master() if get(self.source.count) else tool.current
        self.source.blockSignals(True)
        self.source.clear()
        for name in tool.masters:
            self.source.addItem(name)
        if previous in tool.masters:
            self.source.setCurrentIndex(tool.masters.index(previous))
        self.source.blockSignals(False)
        self.filling = False
        self.rebuild()

    def rebuild(self) -> None:
        """One checkable row per master other than the source."""
        if self.filling:
            return
        others = [m for m in self.tool.masters if m != self.source_master()]
        self.targets.set_rows([(m, "", "", "", "") for m in others], [bool(self.checked.get(m)) for m in others])
        self.update()

    def update(self) -> None:
        """Re-plan from one fresh snapshot and fill the counts in place."""
        tool = self.tool
        self.snapshot, self.edits = None, {}
        if tool.package is None:
            self.subtitle.setText("Open a font first.")
            self.count.setText("")
            self.apply_button.setEnabled(False)
            return
        total = 0
        try:
            self.snapshot = snapshot = fontui.kerning_snapshot(tool.package)
            source = self.source_master()
            chosen = self.chosen_targets()
            self.edits = copy_edits(tool.backends().edit, snapshot.pairs, source, chosen, self.mode_key(),
                                    get(self.percent.value))
            self.subtitle.setText(f"{source} has {len(snapshot.pairs[source])} pairs. Tick the masters that receive them.")
            self.targets.filling = True
            self.targets.view.setSortingEnabled(False)
            for number in range(get(self.targets.view.rowCount)):
                master = self.targets.view.item(number, 0).text()
                target = snapshot.pairs[master]
                numbers = [len(target), "", "", ""]
                if master in self.edits:
                    added, changed, removed = tool.backends().edit.summary(target, self.edits[master])
                    numbers = [len(target), added, changed, removed]
                    total += added + changed + removed
                for column, value in enumerate(numbers, 1):
                    self.targets.view.item(number, column).setText(str(value))
            self.targets.view.setSortingEnabled(True)
            self.targets.filling = False
        except ERRORS as error:
            self.targets.view.setSortingEnabled(True)
            self.targets.filling = False
            self.snapshot, self.edits, chosen = None, {}, []
            self.count.setText(f"{tool.app}: {error}")
            self.apply_button.setEnabled(False)
            return
        n = len(chosen)
        self.count.setText(f"{total} pair edits in {n} master{'s' if n != 1 else ''}" if chosen
                           else "Tick at least one target master")
        self.apply_button.setEnabled(bool(chosen) and total > 0)

    def ready(self) -> bool:
        """The displayed snapshot must contain a nonempty copy plan."""
        return self.snapshot is not None and any(self.edits.values())

    def apply(self) -> bool:
        """Write the displayed plan as one Undo step, then re-read and report each target's counts."""
        edits, snapshot, source = self.edits, self.snapshot, self.source_master()

        def write() -> bool:
            edit = self.tool.backends().edit
            result = {m: edit.summary(snapshot.pairs[m], changes) for m, changes in edits.items()}
            done = self.tool.write(self.ACTION, f"kerning from {source} to {', '.join(edits)}", edits, snapshot)
            self.tool.reload()
            self.tool.say("Copied: " + " · ".join(f"{m} +{a} ~{c} −{r}" for m, (a, c, r) in result.items())
                          if done else f"{self.tool.app}: nothing changed.")
            return done

        done = bool(self.run(write))
        if not done:
            self.snapshot, self.edits = None, {}
            self.apply_button.setEnabled(False)
        return done


__all__ = ["MODES", "TITLE", "CopyPanel", "copy_edits"]
