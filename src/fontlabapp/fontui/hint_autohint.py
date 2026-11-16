# this_file: src/fontlabapp/fontui/hint_autohint.py
# SPDX-License-Identifier: Apache-2.0
"""Run FontLab's PostScript autohinter on the selected glyphs, in one or all
masters.

What it does:
    For each selected glyph and chosen master, the script runs FontLab's own
    autohinter on the layer. It works from the font's hinting settings
    (alignment zones and standard stems). The table shows the horizontal and
    vertical hint counts before and after. FontLab's source does not touch
    TrueType instructions here.

How it works:
    A non-modal panel lists every glyph and master with its hint counts, or
    the reason why the layer is skipped. Apply reads the font again and
    calls the native flLayer.autohint() on every planned layer, all in one
    Undo step through the shared module fly.ap.core.history.glyphs. Read-back reports
    a layer that has an outline but no PostScript hints after the call. The
    hint counts and the panel are shared (fly.ap.hints.postscript,
    fly.ap.contours.selection.panel.model).

Native call caveat:
    FontLab's source shows that autohint switches the package master
    temporarily,
    writes hinting options and stored hinting data, and can attach hints as
    node links. These effects extend beyond the notified layers; the script
    does not check them. TrueType instructions are separate.

Why this design:
    - The hints come from FontLab's own autohinter, not from a script
      algorithm.
    - The script adds what the menu command does not: every master in one
      step, a count of hints before and after, and one Undo step.
    - Automatic layers and glyphs with automatic layers are never edited. A
      base of automatic composites is skipped unless you tick "Edit bases of
      auto glyphs anyway": the change notification makes FontLab rebuild
      those composites, which can drop their anchors and locks, and Undo
      does not restore them. Locked layers and layers without contours are
      skipped.
    - Apply discloses queued ids and their possible date changes. The script
      does not call UpdateAll (fl#8537).

How to use:
    Set the alignment zones and standard stems in Font Info first. Select
    glyphs in the Font window. Run the script. Choose the current master or
    all masters, check the table and press Autohint. Each Apply is recorded
    as one Undo step.

Benefit:
    A whole selection gets fresh PostScript hints in every master, with the
    counts in view, in one step.

Credit:
    Adapted from the author's own FontLab sample, Apache-2.0
    (hints_autohint.py, "Autohint Selected Layers").
"""

from collections.abc import Sequence
from typing import Any

from fontlabapp.studios.hint_tools.autohint import (
    Row as Row,
    _valid as _valid,
    has_outline as has_outline,
    layer_note as layer_note,
    survey as survey,
    autohint as autohint,
    TITLE as TITLE,
    KEY as KEY,
)

def panel_type() -> type:
    """Build the panel class once Qt is available (inside FontLab)."""
    import fontlabapp.core.history.glyphs as history  # noqa: PLR0402 - fontlabapp.__getattr__ is native
    import fontlabapp.masters.layers.writer as layer_writer  # noqa: PLR0402
    import fontlabapp.contours.selection.panel.model as selection_panel  # noqa: PLR0402

    class AutohintPanel(selection_panel.panel_type()):
        """Masters, bases opt-in, hint count table, status and buttons."""

        TITLE, KEY, ACTION = TITLE, KEY, "Autohint"
        HEADERS = ("Glyph · master", "Hints now (h / v)", "After Autohint")

        def build_controls(self) -> None:
            """No own controls; keep the counts after Autohint."""
            self.after: dict[tuple[str, str], tuple[int, int]] = {}

        def plan_rows(self, package: Any, masters: list[str]) -> list[Row]:
            """Plan with the captured auto-layer facts and the bases opt-in."""
            return survey(
                package,
                self.names,
                masters,
                self.facts,
                self.consented(),
            )

        def cells(self, row: Row) -> list[str]:
            """Glyph · master, and the note or the counts now and after."""
            label = f"{row.glyph.name} · {row.master}"
            if row.note:
                return [label, row.note]
            after = self.after.get((str(row.glyph.name), row.master))
            return [
                label,
                "{} / {}".format(*row.before),
                "{} / {}".format(*after) if after else "",
            ]

        def pending(self, todo: Sequence[Row]) -> str:
            """Status before Apply."""
            return (
                f"{layer_writer.plural(len(todo), 'layer')} will be autohinted"
                if todo
                else "Nothing to autohint"
            )

        def write(self, package: Any, rows: list[Row]) -> dict[str, Any]:
            """Autohint with fresh facts. One Undo step."""
            return autohint(rows, history.scan_auto_facts(package), self.consented())

        def on_result(self, result: dict[str, Any]) -> None:
            """Keep the counts after Autohint for the table."""
            self.after = dict(result["after"])

        def on_reselect(self) -> None:
            """Forget the counts of the old selection."""
            self.after = {}

        def result_text(self, result: dict[str, Any]) -> str:
            """Status after Apply; the shared panel appends read-back mismatches."""
            if not result["layers"]:
                return "Nothing to autohint"
            plural = layer_writer.plural
            text = f"Autohinted {plural(result['layers'], 'layer')} of {plural(result['glyphs'], 'glyph')}"
            return text

    return AutohintPanel


def main() -> Any:
    """Open the panel. A second run replaces the first panel."""
    import fontlabapp.core.scripting as scripting  # noqa: PLR0402 - fontlabapp.__getattr__ is native

    return scripting.show_script_dialog(panel_type(), KEY)


if __name__ == "__main__":
    main()
