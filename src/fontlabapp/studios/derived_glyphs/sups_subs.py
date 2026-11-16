# this_file: src/fontlabapp/studios/derived_glyphs/sups_subs.py
# SPDX-License-Identifier: Apache-2.0
"""Sups & subs tab: ``Scripts/Contours/Superior & Inferior Figures.py`` in host mode.

One ``.sups`` or ``.subs`` copy per selected figure (zero-nine), scaled by
Scale 60 % (10-100 %) about the origin and shifted by Vertical shift
(-1000..1000 units; preset 350 for Superior, -150 for Inferior; choosing a
kind takes its preset). Names that are not figures or are sized already
(sups, subs, sinf, numr, dnom) are skipped, as are repeated, missing and
existing targets and auto/composite/empty sources. The rebuild consent and
Use selection behave as in the original. The pure functions below are the
original's, verbatim (only their local ``fly`` imports are module names here).
"""

from collections.abc import Sequence
from typing import Any

from .._kerning_ui import combo, get, row as form_row, spin
from . import _shared
from ._shared import CopiesPanel

#: The names the verbatim originals import inside their functions.
glyph_copies = _shared.Modules("copies")
contour_copy = _shared.Modules("contour_copy")
qt = _shared.Qt

FIGURES = frozenset(
    {"zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"}
)


KINDS = (
    (".sups", "Superior", 350),
    (".subs", "Inferior", -150),
)  # suffix, label, preset shift


SIZED = frozenset(
    {"sups", "subs", "sinf", "numr", "dnom"}
)  # suffixes of figures that are sized already


def naming_for(suffix: str) -> Any:
    """Return the naming function for ``suffix`` (".sups" or ".subs")."""

    def naming(name: str) -> tuple[str, str]:
        parts = name.split(".")
        if parts[0] not in FIGURES:
            return "", "not a figure"
        if SIZED.intersection(parts[1:]):
            return "", "already superior or inferior"
        return name + suffix, ""

    return naming


def survey(
    package: Any,
    names: Sequence[str],
    facts: Any,
    suffix: str = ".sups",
    allow_rebuild: bool = False,
) -> list[Any]:
    """Plan one sized copy per selected figure. Change nothing."""

    return glyph_copies.survey_with(
        package, names, naming_for(suffix), facts, allow_rebuild
    )


def prepare(rows: Sequence[Any], scale: int, shift: int) -> list[Any]:
    """Return the jobs: copies scaled by ``scale`` percent about the origin, then shifted up."""

    factor = scale / 100
    transform = qt.QtGui.QTransform(factor, 0, 0, factor, 0, shift)
    return [
        (
            row.target,
            [
                (
                    m,
                    contour_copy.copy_contours(x, transform),
                    glyph_copies.half_up(x.advanceWidth * factor),
                )
                for m, x in row.layers
            ],
        )
        for row in rows
        if not row.note
    ]


class SupsSubsPanel(CopiesPanel):
    """Kind, scale and vertical shift, dry run, consent, Create glyphs."""

    NOUN = "figures"

    def build_controls(self, form: Any) -> None:
        self.kind = combo(
            self.widget,
            [f"{name} ({suffix})" for suffix, name, _ in KINDS],
            self.contain(self.switch_kind),
        )
        self.factor = spin(
            self.widget, 10, 100, 60, suffix=" %", slot=self.contain(self.refresh)
        )
        self.shift = spin(
            self.widget,
            -1000,
            1000,
            KINDS[0][2],
            suffix=" units",
            slot=self.contain(self.refresh),
        )
        form_row(self.widget, form, "Kind", self.kind)
        form_row(self.widget, form, "Scale", self.factor)
        form_row(self.widget, form, "Vertical shift", self.shift)

    @property
    def UNDO(self) -> str:  # noqa: N802 - the PlanPanel attribute
        return f"create {KINDS[int(get(self.kind.currentIndex))][1].lower()} figures"

    def suffix(self) -> str:
        return KINDS[int(get(self.kind.currentIndex))][0]

    def switch_kind(self, *_: Any) -> None:
        """Take the preset shift of the chosen kind, then plan again."""
        self.shift.blockSignals(True)
        self.shift.setValue(KINDS[int(get(self.kind.currentIndex))][2])
        self.shift.blockSignals(False)
        self.refresh()

    def survey(self, package: Any, facts: Any, allow_rebuild: bool) -> list[Any]:
        return survey(package, self.names or [], facts, self.suffix(), allow_rebuild)

    def jobs(self, rows: list[Any]) -> list[Any]:
        return prepare(rows, int(get(self.factor.value)), int(get(self.shift.value)))


__all__ = [
    "FIGURES",
    "KINDS",
    "SIZED",
    "SupsSubsPanel",
    "naming_for",
    "prepare",
    "survey",
]
