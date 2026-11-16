# this_file: src/fontlabapp/studios/derived_glyphs/small_caps.py
# SPDX-License-Identifier: Apache-2.0
"""Small caps tab: ``Scripts/Contours/Small Caps From Capitals.py`` in host mode.

One ``.sc`` glyph per selected capital (H -> h.sc, H.ss01 -> h.sc.ss01),
contours scaled about the origin by Horizontal 75 % / Vertical 70 %
(10-200 %), advance scaled and rounded half up. Names that are not capitals,
repeated, missing, existing targets and auto/composite/empty sources are
listed and skipped. Rows that may rebuild auto glyphs are skipped unless
"Create even if FontLab may rebuild these auto glyphs" is ticked; Use
selection clears that tick. The pure functions below are the original's,
verbatim (only their local ``fly`` imports are module names here).
Adapted from the author's own FontLab sample, Apache-2.0
(generate_small_caps.py, "Small Caps from Capitals").
"""

from collections.abc import Sequence
from typing import Any

from .._kerning_ui import get, row as form_row, spin
from . import _shared
from ._shared import CopiesPanel

#: The names the verbatim originals import inside their functions.
glyph_copies = _shared.Modules("copies")
contour_copy = _shared.Modules("contour_copy")
qt = _shared.Qt

SUFFIX = ".sc"


def is_capital(name: str) -> bool:
    """True when the base name (before the first dot) starts with a capital letter."""
    base = name.partition(".")[0]
    return base[:1].isupper() and base.lower() != base


def target_name(name: str) -> str:
    """Return the small-cap name: H -> h.sc, H.ss01 -> h.sc.ss01."""
    base, dot, rest = name.partition(".")
    return base.lower() + SUFFIX + (dot + rest if dot else "")


def naming(name: str) -> tuple[str, str]:
    """Return (new name, problem) for a selected glyph name."""
    if not is_capital(name):
        return "", "not a capital"
    return target_name(name), ""


def survey(
    package: Any, names: Sequence[str], facts: Any, allow_rebuild: bool = False
) -> list[Any]:
    """Plan one small cap per selected capital. Change nothing."""

    return glyph_copies.survey_with(package, names, naming, facts, allow_rebuild)


def prepare(rows: Sequence[Any], x_scale: int, y_scale: int) -> list[Any]:
    """Return the jobs: copies scaled by the percentages about the origin."""

    sx, sy = x_scale / 100, y_scale / 100
    transform = qt.QtGui.QTransform(sx, 0, 0, sy, 0, 0)
    return [
        (
            row.target,
            [
                (
                    m,
                    contour_copy.copy_contours(x, transform),
                    glyph_copies.half_up(x.advanceWidth * sx),
                )
                for m, x in row.layers
            ],
        )
        for row in rows
        if not row.note
    ]


class SmallCapsPanel(CopiesPanel):
    """Horizontal and vertical scale, dry run, consent, Create glyphs."""

    NOUN = "capitals"
    UNDO = "create small caps"

    def build_controls(self, form: Any) -> None:
        self.x_scale = spin(
            self.widget, 10, 200, 75, suffix=" %", slot=self.contain(self.refresh)
        )
        self.y_scale = spin(
            self.widget, 10, 200, 70, suffix=" %", slot=self.contain(self.refresh)
        )
        form_row(self.widget, form, "Horizontal scale", self.x_scale)
        form_row(self.widget, form, "Vertical scale", self.y_scale)

    def survey(self, package: Any, facts: Any, allow_rebuild: bool) -> list[Any]:
        return survey(package, self.names or [], facts, allow_rebuild)

    def jobs(self, rows: list[Any]) -> list[Any]:
        return prepare(rows, int(get(self.x_scale.value)), int(get(self.y_scale.value)))


__all__ = [
    "SUFFIX",
    "SmallCapsPanel",
    "is_capital",
    "naming",
    "prepare",
    "survey",
    "target_name",
]
