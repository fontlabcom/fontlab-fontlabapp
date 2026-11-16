# this_file: src/fontlabapp/studios/derived_glyphs/compat_tabular.py
# SPDX-License-Identifier: Apache-2.0
'Create tabular (.tf) copies of the selected figures, with one shared width per\nmaster.\n\nWhat it does:\n    For each selected figure (zero to nine, also with a suffix such as\n    one.osf) the script creates a new glyph with ".tf" added to the name, on\n    every master. In each master all new glyphs get one advance width: the\n    widest selected figure of that master plus an extra amount. The figure\n    outline is copied and centred in that width. The source figures do not\n    change.\n\nHow it works:\n    A non-modal panel lists every selected glyph with its new name, or the\n    reason why it is skipped. Create checks the font again. FontLab\'s own\n    Add Glyph command makes each new glyph with its master layers and the\n    shared widths. Then one step through the shared module fly.ap.core.history.glyphs\n    adds the centred copies to all new layers. The centring keeps the\n    outline on whole units; an odd unit of white space goes to the right\n    side. The copy keeps node names and raw node flags, which a FontLab\n    contour copy can drop (fl#8569). After the write the script reads every\n    new layer back, and checks that no automatic glyph of the font changed.\n    The creation, the contour copy and the panel are shared\n    (fly.ap.glyphs.copies, fly.ap.contours.copy).\n\nCopy limits:\n    Anchors are not copied. Add the required anchors to the new glyphs before\n    building accented composites.\n    Only node names and raw node flags are repaired (fl#8569); selection is\n    cleared. Other node properties and contour names are not repaired.\n    Copied contours are merged into one element; source element names and\n    notes are not copied.\n\nWhy this design:\n    - New glyphs, not changed figures: proportional and tabular figures can\n      then live side by side, as the OpenType tnum feature expects. To make\n      the existing figures tabular in place, use Metrics > Tabular Width.\n    - A figure needs a layer with contours on every master, with no\n      components and no automatic layer. Otherwise the figure is listed and\n      skipped, so the new glyphs stay compatible across masters.\n    - A target name that exists is never overwritten.\n    - Create discloses queued ids and their possible date changes. The script\n      does not call UpdateAll (fl#8537).\n    - FontLab can rebuild an automatic glyph when a new name appears. When\n      the font has automatic glyphs without a recipe whose names carry the\n      new suffix, the row shows "may rebuild auto ..." and is skipped unless\n      you tick "Create even if FontLab may rebuild these auto glyphs". Use\n      selection clears the tick.\n    - Each new glyph is recorded as its own Undo step, and the outlines as\n      one more Undo step.\n\nHow to use:\n    Select the figures in the Font window. Run the script. Set the extra\n    width, check the table and press Create. Narrow figures such as one can\n    then need redrawing in their wider space.\n\nBenefit:\n    A complete, compatible set of tabular figures to refine, in one step.\n\nCredit:\n    Adapted from the author\'s own FontLab sample, Apache-2.0\n    (generate_tabular_copies.py, "Tabular Figure Copies").'
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

TITLE = "Tabular Figure Copies"
KEY = "generate_tabular_copies"
SUFFIX = ".tf"
FIGURES = frozenset(
    {"zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"}
)
def naming(name: str):
    """Delegate the retained callable contract to the studio model."""
    from fontlabapp.studios.derived_glyphs import tabular as implementation
    return implementation.naming(name)


def survey(package: Any, names: Sequence[str], facts: Any, allow_rebuild: bool=False):
    """Delegate the retained callable contract to the studio model."""
    from fontlabapp.studios.derived_glyphs import tabular as implementation
    return implementation.survey(package, names, facts, allow_rebuild)


def tabular_widths(rows: Sequence[Any], extra: int):
    """Delegate the retained callable contract to the studio model."""
    from fontlabapp.studios.derived_glyphs import tabular as implementation
    return implementation.tabular_widths(rows, extra)


def centring_shift(layer: Any, width: int):
    """Delegate the retained callable contract to the studio model."""
    from fontlabapp.studios.derived_glyphs import tabular as implementation
    return implementation.centring_shift(layer, width)


def prepare(rows: Sequence[Any], widths: dict[str, int]):
    """Delegate the retained callable contract to the studio model."""
    from fontlabapp.studios.derived_glyphs import tabular as implementation
    return implementation.prepare(rows, widths)

def panel_type() -> type:
    """Build the panel class once Qt is available (inside FontLab)."""
    from fontlabapp.fontui import outline_generators_backends
    glyph_copies = outline_generators_backends().glyph_copies
    from fontlabapp.fontui import outline_generators_backends
    qt = outline_generators_backends().qt

    QtGui = qt.QtGui

    class TabularCopiesPanel(glyph_copies.panel_type()):
        """Extra width, preview table, status and buttons."""

        TITLE, KEY, NOUN = TITLE, KEY, "figures"

        def build_controls(self) -> None:
            """Extra width; a change plans again."""
            self.extra = QtGui.QSpinBox()
            self.extra.setRange(-200, 400)
            self.extra.setSuffix(" units")
            self.extra.setValue(0)
            self.add_row("Extra width", self.extra)
            self.watch(self.extra.valueChanged)

        def survey(self, package: Any, facts: Any, allow_rebuild: bool) -> list[Any]:
            """Plan one tabular copy per selected figure."""
            return survey(package, self.names, facts, allow_rebuild)

        def jobs(self, rows: list[Any]) -> list[Any]:
            """Centred copies of the ready rows in the shared widths."""
            return prepare(rows, tabular_widths(rows, int(self.extra.value)))

        def intro(self) -> str:
            """Subtitle: the shared width per master."""
            widths = tabular_widths(self.rows, int(self.extra.value))
            shown = ", ".join(f"{m} {w}" for m, w in widths.items())
            return (
                f"Shared width per master: {shown}"
                if widths
                else "No figure qualifies."
            )

    return TabularCopiesPanel

def main() -> Any:
    """Open the panel. A second run replaces the first panel."""
    import fontlabapp.core.scripting as scripting  # noqa: PLR0402 - avoid native parent fallback

    return scripting.show_script_dialog(panel_type(), KEY)
