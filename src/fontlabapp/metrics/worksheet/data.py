# this_file: src/fontlabapp/metrics/worksheet/data.py
# SPDX-License-Identifier: Apache-2.0
"""Immutable local spacing recipes and complete captured advance facts.

The two original numeric-delegate policies share arithmetic, not storage types.
Candidate advances are a decision aid. This module never changes a font.
"""

from dataclasses import dataclass
from math import isfinite

_DEFAULTS = ((1, 2), (2, 4), (3, 6), (4, 8))


def defaults(official: bool) -> tuple:
    """Keep part2 string items and part3 integer values distinct."""
    return (
        _DEFAULTS
        if official
        else tuple(tuple(str(v) for v in row) for row in _DEFAULTS)
    )


def increments(rows: tuple) -> tuple[int, ...]:
    """Compute exactly four A-times-B products after checking local model facts."""
    if len(rows) != 4 or any(len(row) != 2 for row in rows):
        raise ValueError("The worksheet needs four rows and two columns.")
    values = []
    for row in rows:
        pair = []
        for value in row:
            if type(value) not in (int, str):
                raise TypeError(
                    "A worksheet factor must be an integer or an original string item."
                )
            number = int(value)
            if not 0 <= number <= 100:
                raise ValueError("Factors must be in the inclusive range 0 to 100.")
            pair.append(number)
        values.append(pair[0] * pair[1])
    return tuple(values)


@dataclass(frozen=True)
class Baseline:
    """One ordered selected glyph-layer occurrence; no native handles retained."""

    package_id: int
    glyph_id: int
    layer_id: int
    glyph_name: str
    layer_name: str
    width: float

    def __post_init__(self) -> None:
        if not isfinite(self.width):
            raise ValueError("A selected layer has a non-finite advance width.")


@dataclass(frozen=True)
class Snapshot:
    """Stable package/master/view context and every selected occurrence."""

    context: tuple
    rows: tuple[Baseline, ...]


def render(snapshot: Snapshot | None, rows: tuple) -> str:
    """Show every baseline and four candidate advances in a selectable report."""
    deltas = increments(rows)
    lines = [
        "Local candidates, not applied to font metrics.",
        "Increments: " + ", ".join(map(str, deltas)),
    ]
    if snapshot is None:
        lines.append(
            "No captured selection. Edit the factors or use Refresh Selection."
        )
    else:
        lines.append(
            f"Captured package {snapshot.context[0]}, master {snapshot.context[1]!r}."
        )
        for number, row in enumerate(snapshot.rows, 1):
            candidates = ", ".join(repr(row.width + value) for value in deltas)
            lines.append(
                f"{number}. {row.glyph_name} / {row.layer_name} [glyph {row.glyph_id}, layer {row.layer_id}]: baseline {row.width!r}; candidates {candidates}"
            )
    return "\n".join(lines)
