# this_file: src/fontlabapp/metrics/tabular_width/model.py
# SPDX-License-Identifier: Apache-2.0
"""Check actual selected-layer advances, adapted from Pedro Arilla.

Compare exact widths; metrics keys and automatic spacing are not interpreted.
The first actual selected-layer occurrence supplies the reference, including
repeated editor slots and per-slot layers. Native qualification remains open.
Only immutable plain values leave the boundary. This report calls no font
writers; native getter side effects still require preservation qualification.
See NOTICE for the preserved source and license provenance.
"""

from dataclasses import dataclass
from math import isfinite
from time import monotonic, strftime

import fontlabapp.masters.layers.selection as selection


@dataclass(frozen=True)
class WidthRow:
    """One selected glyph and its unrounded advance comparison."""

    name: str
    width: float
    matches: bool


@dataclass(frozen=True)
class WidthReport:
    """Ordered rows and the original same/different totals at capture time."""

    rows: tuple[WidthRow, ...]
    time: str

    @property
    def same(self) -> int:
        """Count all matching rows, including the reference row."""
        return sum(row.matches for row in self.rows)

    @property
    def different(self) -> int:
        """Count rows whose actual advance differs from the reference."""
        return len(self.rows) - self.same


def compare(values: tuple[tuple[str, float], ...], time: str) -> WidthReport:
    """Compare every selected layer against the first, without rounding."""
    if not values:
        raise ValueError("Select glyphs in the Font window first.")
    if any(not isfinite(width) for _, width in values):
        raise ValueError("A selected layer has a non-finite advance width.")
    reference = values[0][1]
    return WidthReport(
        tuple(WidthRow(name, width, width == reference) for name, width in values), time
    )


def render(report: WidthReport) -> str:
    """Keep the original time heading, per-glyph status and result totals.

    Use repr for widths rather than the original integer formatting, so a
    fractional difference remains visible while the comparison stays exact.
    """
    lines = ["Tabular width checker @ " + report.time]
    lines.extend(
        f"{chr(0x2705) if row.matches else chr(0x274C)} {row.name} ({row.width!r})"
        for row in report.rows
    )
    return "\n".join(
        [
            *lines,
            "Result:",
            f"{report.same} glyphs are on same width.",
            f"{report.different} glyphs are on different width.",
        ]
    )


def _read(selected: selection.LayerSelection, deadline: float) -> tuple:
    """Read exact selected-layer identities/advances without FontGate caches."""
    rows = []
    for occurrence in selected.occurrences:
        _check_deadline(deadline)
        glyph, layer = occurrence.glyph, occurrence.layer
        if (
            glyph.isNull
            or layer.isNull
            or int(glyph.id) != occurrence.glyph_id
            or int(layer.id) != occurrence.layer_id
            or str(glyph.name) != occurrence.glyph_name
            or str(layer.name) != occurrence.layer_name
            or int(glyph.package.id) != occurrence.package_id
        ):
            raise ValueError("A selected glyph/layer identity changed; refresh.")
        rows.append(
            (
                occurrence.glyph_name,
                occurrence.glyph_id,
                occurrence.layer_id,
                float(layer.advanceWidth),
            )
        )
        _check_deadline(deadline)
    return tuple(rows)


def _check_deadline(deadline: float) -> None:
    """Fail at a Python checkpoint; never truncate the selected glyph domain."""
    if monotonic() >= deadline:
        raise TimeoutError("Width scan exceeded its deadline; no partial report.")


def capture() -> WidthReport:
    """Read actual Font/Glyph-window selected layers, preserving ordered repeats.

    Read every width twice and fence final selection/document context. One2s
    deadline covers the whole action. Native calls cannot be preempted; Python
    checkpoints diagnose overruns. The first actual occurrence is the reference;
    no CurrentGlyph fallback, sorting, deduplication or partial result is used.
    Native preservation/order/focus qualification remains pending.
    """
    deadline = monotonic() + 2.0
    first_selection = selection.capture(deadline)
    if not first_selection.occurrences:
        raise ValueError("Select glyph layers before checking tabular widths.")
    first = _read(first_selection, deadline)
    second_selection = selection.capture(deadline)
    second = _read(second_selection, deadline)
    final_selection = selection.capture(deadline)
    context = selection.document_context(deadline)
    _check_deadline(deadline)
    if (
        first_selection != second_selection
        or second_selection != final_selection
        or context != final_selection.context
        or first != second
    ):
        raise ValueError(
            "Font, master, selection or widths changed; refresh the report."
        )
    report = compare(
        tuple((name, width) for name, _, _, width in first), strftime("%H:%M:%S")
    )
    _check_deadline(deadline)
    return report
