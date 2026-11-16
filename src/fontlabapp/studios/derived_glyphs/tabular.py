# this_file: src/fontlabapp/studios/derived_glyphs/tabular.py
# SPDX-License-Identifier: Apache-2.0
"""Tabular figures tab: ``Scripts/Contours/Tabular Figure Copies.py`` in host mode.

One ``.tf`` copy per selected figure. Every copy on a master gets one shared
width: the widest selected figure on that master (rounded half up) plus
Extra width (-200..400 units, default 0); each outline is centred in it.
Names that are not figures or are tabular already are skipped, as are
repeated, missing and existing targets and auto/composite/empty sources.
The rebuild consent and Use selection behave as in the original. The pure
functions below are the original's, verbatim (only their local ``fly``
imports are module names here).
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

SUFFIX = ".tf"


FIGURES = frozenset(
    {"zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"}
)


def naming(name: str) -> tuple[str, str]:
    """Return (new name, problem) for a selected glyph name."""
    parts = name.split(".")
    if parts[0] not in FIGURES:
        return "", "not a figure"
    if "tf" in parts[1:]:
        return "", "already tabular"
    return name + SUFFIX, ""


def survey(
    package: Any, names: Sequence[str], facts: Any, allow_rebuild: bool = False
) -> list[Any]:
    """Plan one tabular copy per selected figure. Change nothing."""

    return glyph_copies.survey_with(package, names, naming, facts, allow_rebuild)


def tabular_widths(rows: Sequence[Any], extra: int) -> dict[str, int]:
    """Map each master to the widest source advance (rounded half up) plus ``extra``."""

    widths: dict[str, int] = {}
    for row in rows:
        if row.note:
            continue
        for master, layer in row.layers:
            widths[master] = max(
                widths.get(master, 0), glyph_copies.half_up(layer.advanceWidth)
            )
    return {master: width + extra for master, width in widths.items()}


def centring_shift(layer: Any, width: int) -> int:
    """Return the whole-unit x shift that centres the outline in ``width``.

    The left side becomes (width - ink width) // 2; an odd unit goes right.
    """

    box = layer.boundingBox
    left = glyph_copies.half_up(box.x())
    ink = glyph_copies.half_up(box.x() + box.width()) - left
    return (width - ink) // 2 - left


def prepare(rows: Sequence[Any], widths: dict[str, int]) -> list[Any]:
    """Return the jobs: centred contour copies and the shared width per master."""

    jobs: list[Any] = []
    for row in rows:
        if row.note:
            continue
        layers = []
        for master, layer in row.layers:
            move = qt.QtGui.QTransform(
                1, 0, 0, 1, centring_shift(layer, widths[master]), 0
            )
            layers.append(
                (master, contour_copy.copy_contours(layer, move), widths[master])
            )
        jobs.append((row.target, layers))
    return jobs


class TabularPanel(CopiesPanel):
    """Extra width, shared widths in the subtitle, dry run, consent, Create glyphs."""

    NOUN = "figures"
    UNDO = "create tabular figures"

    def build_controls(self, form: Any) -> None:
        self.extra = spin(
            self.widget, -200, 400, 0, suffix=" units", slot=self.contain(self.refresh)
        )
        form_row(self.widget, form, "Extra width", self.extra)

    def survey(self, package: Any, facts: Any, allow_rebuild: bool) -> list[Any]:
        return survey(package, self.names or [], facts, allow_rebuild)

    def jobs(self, rows: list[Any]) -> list[Any]:
        return prepare(rows, tabular_widths(rows, int(get(self.extra.value))))

    def intro(self) -> str:
        """Subtitle: the shared width per master (the original's text)."""
        widths = tabular_widths(self.rows, int(get(self.extra.value)))
        shown = ", ".join(f"{m} {w}" for m, w in widths.items())
        return f"Shared width per master: {shown}" if widths else "No figure qualifies."


__all__ = [
    "FIGURES",
    "SUFFIX",
    "TabularPanel",
    "centring_shift",
    "naming",
    "prepare",
    "survey",
    "tabular_widths",
]
