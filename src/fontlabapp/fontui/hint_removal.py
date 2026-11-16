# this_file: src/fontlabapp/fontui/hint_removal.py
# SPDX-License-Identifier: Apache-2.0
"""Remove PostScript stem hints from the selected glyphs, horizontal and/or
vertical.

What it does:
    For each selected glyph and chosen master, the script removes the
    horizontal hints, the vertical hints or both from the layer. FontLab's
    source does not touch plain guidelines or TrueType instructions here. The
    table shows the hint counts before and after.

How it works:
    A non-modal panel lists every glyph and master with its hint counts, or
    the reason why the layer is skipped. A layer without hints in the chosen
    directions is listed and skipped. Apply reads the font again and calls
    the native flLayer.removeHints(horizontal, vertical) on every planned
    layer, all in one Undo step through the shared module fly.ap.core.history.glyphs.
    After the write it counts the hints again and reports any layer that
    still has hints in a chosen direction. The hint counts and the panel are
    shared (fly.ap.hints.postscript, fly.ap.contours.selection.panel.model).

Why this design:
    - The removal is FontLab's own call, so hints are removed exactly as the
      menu command removes them.
    - The script adds what the menu command does not: every master in one
      step, one direction only, the counts in view and one Undo step.
    - Automatic layers and glyphs with automatic layers are never edited. A
      base of automatic composites is skipped unless you tick "Edit bases of
      auto glyphs anyway": the change notification makes FontLab rebuild
      those composites, which can drop their anchors and locks, and Undo
      does not restore them. Locked layers are skipped.
    - Apply discloses queued ids and their possible date changes. The script
      does not call UpdateAll (fl#8537).

How to use:
    Select glyphs in the Font window. Run the script. Tick the directions,
    choose the current master or all masters, check the table and press
    Remove Hints. Each Apply is recorded as one Undo step.

Benefit:
    Clean hint-free layers before a new autohint pass or a TrueType-only
    export, in every master, in one step.

Credit:
    Adapted from the author's own FontLab sample, Apache-2.0
    (hints_remove.py, "Remove PostScript Hints").
"""

from collections.abc import Sequence
from typing import Any

from fontlabapp.studios.hint_tools.removal import (
    Row as Row,
    _valid as _valid,
    chosen as chosen,
    direction_word as direction_word,
    layer_note as layer_note,
    survey as survey,
    remove_hints as remove_hints,
    TITLE as TITLE,
    KEY as KEY,
)

def panel_type() -> type:
    """Build the panel class once Qt is available (inside FontLab)."""
    import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - fontlabapp.__getattr__ is native
    import fontlabapp.masters.layers.writer as layer_writer  # noqa: PLR0402
    import fontlabapp.contours.selection.panel.model as selection_panel  # noqa: PLR0402
    from fontlabapp import _native

    qt = _native("PythonQt")

    QtGui = qt.QtGui

    class RemoveHintsPanel(selection_panel.panel_type()):
        """Directions, masters, bases opt-in, hint count table, status and buttons."""

        TITLE, KEY, ACTION = TITLE, KEY, "Remove Hints"
        HEADERS = ("Glyph · master", "Hints now (h / v)", "After removal")

        def build_controls(self) -> None:
            """Horizontal and vertical direction ticks, both on."""
            self.horizontal = QtGui.QCheckBox("Horizontal hints")
            self.vertical = QtGui.QCheckBox("Vertical hints")
            for box in (self.horizontal, self.vertical):
                box.setChecked(True)
            self.add_row("Remove", self.horizontal, self.vertical)
            self.watch(self.horizontal.toggled)
            self.watch(self.vertical.toggled)

        def directions(self) -> tuple[bool, bool]:
            """Return the ticked (horizontal, vertical) directions."""
            return bool(self.horizontal.isChecked()), bool(self.vertical.isChecked())

        def plan_rows(self, package: Any, masters: list[str]) -> list[Row]:
            """Plan with the captured auto-layer facts, the bases opt-in and the directions."""
            facts = self.facts
            return survey(
                package,
                self.names,
                masters,
                facts,
                self.consented(),
                *self.directions(),
            )

        def cells(self, row: Row) -> list[str]:
            """Glyph · master, and the note or the counts now and after removal."""
            label = f"{row.glyph.name} · {row.master}"
            if row.note:
                return [label, row.note]
            horizontal, vertical = self.directions()
            h, v = row.before
            return [
                label,
                f"{h} / {v}",
                f"{0 if horizontal else h} / {0 if vertical else v}",
            ]

        def pending(self, todo: Sequence[Row]) -> str:
            """Status before Apply."""
            return (
                f"{layer_writer.plural(len(todo), 'layer')} will lose hints"
                if todo
                else "Nothing to remove"
            )

        def write(self, package: Any, rows: list[Row]) -> dict[str, Any]:
            """Remove the hints with fresh facts. One Undo step."""
            facts = history.scan_auto_facts(package)
            return remove_hints(rows, *self.directions(), facts, self.consented())

        def result_text(self, result: dict[str, Any]) -> str:
            """Status after Apply."""
            if not result["layers"]:
                return "Nothing to remove"
            plural = layer_writer.plural
            return (
                f"Removed {plural(result['removed'], 'hint')} from {plural(result['layers'], 'layer')} "
                f"of {plural(result['glyphs'], 'glyph')}"
            )

    return RemoveHintsPanel


def main() -> Any:
    """Open the panel. A second run replaces the first panel."""
    import fontlabapp.core.scripting as scripting  # noqa: PLR0402 - fontlabapp.__getattr__ is native

    return scripting.show_script_dialog(panel_type(), KEY)


if __name__ == "__main__":
    main()
