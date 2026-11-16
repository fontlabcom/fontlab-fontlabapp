# this_file: src/fontlabapp/studios/derived_glyphs/compat_sups_subs.py
# SPDX-License-Identifier: Apache-2.0
'Create superior (.sups) or inferior (.subs) copies of the selected figures.\n\nWhat it does:\n    For each selected figure (zero to nine, also with a suffix) the script\n    creates a new glyph with ".sups" or ".subs" added to the name, on every\n    master. The outline is scaled by one factor and moved up or down; the\n    advance width is scaled by the same factor. The source figures do not\n    change.\n\nHow it works:\n    A non-modal panel lists every selected glyph with its new name, or the\n    reason why it is skipped. Choose Superior or Inferior: the vertical shift\n    takes the usual preset (350 or -150 units), which you can change. Create\n    checks the font again. FontLab\'s own Add Glyph command makes each new\n    glyph with its master layers and widths (rounded half up). Then one step\n    through the shared module fly.ap.core.history.glyphs adds the scaled copies to all\n    new layers. The copy keeps node names and raw node flags, which a\n    FontLab contour copy can drop (fl#8569). After the write the script\n    reads every new layer back, and checks that no automatic glyph of the\n    font changed. The creation, the contour copy and the panel are shared\n    (fly.ap.glyphs.copies, fly.ap.contours.copy).\n\nCopy limits:\n    Anchors are not copied. Add the required anchors to the new glyphs before\n    building accented composites.\n    Only node names and raw node flags are repaired (fl#8569); selection is\n    cleared. Other node properties and contour names are not repaired.\n    Copied contours are merged into one element; source element names and\n    notes are not copied.\n\nWhy this design:\n    - Scaling about the baseline origin, then one vertical shift, keeps all\n      new figures on one common baseline, as the sups and subs features\n      expect.\n    - Scaled figures come out lighter than the originals. The result is a\n      starting point for drawing, not finished superiors.\n    - A figure needs a layer with contours on every master, with no\n      components and no automatic layer. Otherwise the figure is listed and\n      skipped, so the new glyphs stay compatible across masters.\n    - A target name that exists is never overwritten. Create discloses queued\n      ids and their possible date changes. The script does not call\n      UpdateAll (fl#8537).\n    - FontLab can rebuild an automatic glyph when a new name appears. When\n      the font has automatic glyphs without a recipe whose names carry the\n      new suffix, the row shows "may rebuild auto ..." and is skipped unless\n      you tick "Create even if FontLab may rebuild these auto glyphs". Use\n      selection clears the tick.\n    - Each new glyph is recorded as its own Undo step, and the outlines as\n      one more Undo step.\n\nHow to use:\n    Select the figures in the Font window. Run the script. Choose Superior or\n    Inferior, set the scale and the shift, check the table and press Create.\n\nBenefit:\n    A compatible set of superior or inferior figures to refine, in every\n    master, in one step.\n\nCredit:\n    Adapted from the author\'s own FontLab sample, Apache-2.0\n    (generate_superiors.py, "Superior & Inferior Figures").'
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

TITLE = "Superior & Inferior Figures"
KEY = "generate_superiors"
FIGURES = frozenset(
    {"zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"}
)
KINDS = (
    (".sups", "Superior", 350),
    (".subs", "Inferior", -150),
)
SIZED = frozenset(
    {"sups", "subs", "sinf", "numr", "dnom"}
)
def naming_for(suffix: str):
    """Delegate the retained callable contract to the studio model."""
    from fontlabapp.studios.derived_glyphs import sups_subs as implementation
    return implementation.naming_for(suffix)


def survey(package: Any, names: Sequence[str], facts: Any, suffix: str='.sups', allow_rebuild: bool=False):
    """Delegate the retained callable contract to the studio model."""
    from fontlabapp.studios.derived_glyphs import sups_subs as implementation
    return implementation.survey(package, names, facts, suffix, allow_rebuild)


def prepare(rows: Sequence[Any], scale: int, shift: int):
    """Delegate the retained callable contract to the studio model."""
    from fontlabapp.studios.derived_glyphs import sups_subs as implementation
    return implementation.prepare(rows, scale, shift)

def panel_type() -> type:
    """Build the panel class once Qt is available (inside FontLab)."""
    from fontlabapp.fontui import outline_generators_backends
    glyph_copies = outline_generators_backends().glyph_copies
    from fontlabapp.fontui import outline_generators_backends
    qt = outline_generators_backends().qt

    QtGui = qt.QtGui

    class SuperiorsPanel(glyph_copies.panel_type()):
        """Kind, scale, shift, preview table, status and buttons."""

        TITLE, KEY, NOUN = TITLE, KEY, "figures"

        def build_controls(self) -> None:
            """Kind, scale and vertical shift; a new kind takes its preset shift."""
            self.kind = QtGui.QComboBox()
            for suffix, label, _ in KINDS:
                self.kind.addItem(f"{label} ({suffix})")
            self.factor = QtGui.QSpinBox()
            self.factor.setRange(10, 100)
            self.factor.setSuffix(" %")
            self.factor.setValue(60)
            self.shift = QtGui.QSpinBox()
            self.shift.setRange(-1000, 1000)
            self.shift.setSuffix(" units")
            self.shift.setValue(KINDS[0][2])
            self.add_row("Kind", self.kind)
            self.add_row("Scale", self.factor)
            self.add_row("Vertical shift", self.shift)
            self.watch(self.kind.currentIndexChanged, self.switch_kind)

        def suffix(self) -> str:
            """Return the chosen suffix."""
            return KINDS[self.kind.currentIndex][0]

        def switch_kind(self) -> None:
            """Take the preset shift of the chosen kind, then plan again."""
            self.shift.setValue(KINDS[self.kind.currentIndex][2])
            self.refresh()

        def survey(self, package: Any, facts: Any, allow_rebuild: bool) -> list[Any]:
            """Plan one sized copy per selected figure with the chosen suffix."""
            return survey(package, self.names, facts, self.suffix(), allow_rebuild)

        def jobs(self, rows: list[Any]) -> list[Any]:
            """Scaled and shifted copies of the ready rows."""
            return prepare(rows, int(self.factor.value), int(self.shift.value))

    return SuperiorsPanel

def main() -> Any:
    """Open the panel. A second run replaces the first panel."""
    import fontlabapp.core.scripting as scripting  # noqa: PLR0402 - avoid native parent fallback

    return scripting.show_script_dialog(panel_type(), KEY)
