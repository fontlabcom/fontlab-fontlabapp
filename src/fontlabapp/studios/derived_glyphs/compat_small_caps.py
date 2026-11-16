# this_file: src/fontlabapp/studios/derived_glyphs/compat_small_caps.py
# SPDX-License-Identifier: Apache-2.0
'Create small-cap glyphs (h.sc, a.sc, ...) from the selected capitals.\n\nWhat it does:\n    For each selected capital the script creates a small-cap glyph on every\n    master: H becomes h.sc, H.ss01 becomes h.sc.ss01. The outline is scaled\n    by separate horizontal and vertical factors; the advance width is scaled\n    horizontally. The capitals do not change.\n\nHow it works:\n    A non-modal panel lists every selected glyph with its new name, or the\n    reason why it is skipped. Create checks the font again. FontLab\'s own\n    Add Glyph command makes each new glyph with its master layers and widths\n    (rounded half up). Then one step through the shared module\n    fly.ap.core.history.glyphs adds the scaled copies to all new layers. The copy keeps\n    node names and raw node flags, which a FontLab contour copy can drop\n    (fl#8569). After the write the script reads every new layer back, and\n    checks that no automatic glyph of the font changed. The creation, the\n    contour copy and the panel are shared (fly.ap.glyphs.copies,\n    fly.ap.contours.copy).\n\nCopy limits:\n    Anchors are not copied. Add the required anchors to the new glyphs before\n    building accented composites.\n    Only node names and raw node flags are repaired (fl#8569); selection is\n    cleared. Other node properties and contour names are not repaired.\n    Copied contours are merged into one element; source element names and\n    notes are not copied.\n\nWhy this design:\n    - The name is the lowercase base plus ".sc", the usual naming for the\n      smcp and c2sc features.\n    - A larger horizontal than vertical factor keeps vertical stems\n      relatively heavier, so the small caps do not look too light at once.\n      The result is a starting point for drawing, not finished small caps.\n    - A capital needs a layer with contours on every master, with no\n      components and no automatic layer. Otherwise it is listed and skipped,\n      so the new glyphs stay compatible across masters. Accented capitals\n      are usually components: build their small caps from the new bases.\n    - A target name that exists is never overwritten. Create discloses queued\n      ids and their possible date changes. The script does not call\n      UpdateAll (fl#8537).\n    - FontLab can rebuild an automatic glyph when a new name appears. When\n      the font has automatic glyphs without a recipe whose names carry the\n      new suffix (such as eacute.sc), the row shows "may rebuild auto ..."\n      and is skipped unless you tick "Create even if FontLab may rebuild\n      these auto glyphs". Use selection clears the tick.\n    - Each new glyph is recorded as its own Undo step, and the outlines as\n      one more Undo step.\n\nHow to use:\n    Select capitals in the Font window. Run the script. Set the horizontal\n    and vertical scale, check the table and press Create.\n\nBenefit:\n    A compatible set of small caps to refine, in every master, in one step.\n\nCredit:\n    Adapted from the author\'s own FontLab sample, Apache-2.0\n    (generate_small_caps.py, "Small Caps from Capitals").'
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

TITLE = "Small Caps From Capitals"
KEY = "generate_small_caps"
SUFFIX = ".sc"
def is_capital(name: str):
    """Delegate the retained callable contract to the studio model."""
    from fontlabapp.studios.derived_glyphs import small_caps as implementation
    return implementation.is_capital(name)


def target_name(name: str):
    """Delegate the retained callable contract to the studio model."""
    from fontlabapp.studios.derived_glyphs import small_caps as implementation
    return implementation.target_name(name)


def naming(name: str):
    """Delegate the retained callable contract to the studio model."""
    from fontlabapp.studios.derived_glyphs import small_caps as implementation
    return implementation.naming(name)


def survey(package: Any, names: Sequence[str], facts: Any, allow_rebuild: bool=False):
    """Delegate the retained callable contract to the studio model."""
    from fontlabapp.studios.derived_glyphs import small_caps as implementation
    return implementation.survey(package, names, facts, allow_rebuild)


def prepare(rows: Sequence[Any], x_scale: int, y_scale: int):
    """Delegate the retained callable contract to the studio model."""
    from fontlabapp.studios.derived_glyphs import small_caps as implementation
    return implementation.prepare(rows, x_scale, y_scale)

def panel_type() -> type:
    """Build the panel class once Qt is available (inside FontLab)."""
    from fontlabapp.fontui import outline_generators_backends
    glyph_copies = outline_generators_backends().glyph_copies
    from fontlabapp.fontui import outline_generators_backends
    qt = outline_generators_backends().qt

    QtGui = qt.QtGui

    class SmallCapsPanel(glyph_copies.panel_type()):
        """Horizontal and vertical scale, preview table, status and buttons."""

        TITLE, KEY, NOUN = TITLE, KEY, "capitals"

        def build_controls(self) -> None:
            """Horizontal and vertical scale in percent."""
            self.x_scale, self.y_scale = QtGui.QSpinBox(), QtGui.QSpinBox()
            for spin, value in ((self.x_scale, 75), (self.y_scale, 70)):
                spin.setRange(10, 200)
                spin.setSuffix(" %")
                spin.setValue(value)
            self.add_row("Horizontal scale", self.x_scale)
            self.add_row("Vertical scale", self.y_scale)

        def survey(self, package: Any, facts: Any, allow_rebuild: bool) -> list[Any]:
            """Plan one small cap per selected capital."""
            return survey(package, self.names, facts, allow_rebuild)

        def jobs(self, rows: list[Any]) -> list[Any]:
            """Scaled copies of the ready rows."""
            return prepare(rows, int(self.x_scale.value), int(self.y_scale.value))

    return SmallCapsPanel

def main() -> Any:
    """Open the panel. A second run replaces the first panel."""
    import fontlabapp.core.scripting as scripting  # noqa: PLR0402 - avoid native parent fallback

    return scripting.show_script_dialog(panel_type(), KEY)
