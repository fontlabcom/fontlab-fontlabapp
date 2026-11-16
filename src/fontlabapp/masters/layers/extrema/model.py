# this_file: src/fontlabapp/masters/layers/extrema/model.py
# SPDX-License-Identifier: MIT AND Apache-2.0
"""Shared ordered layer extrema for two complete glyph-proof workflows.

Sources: Simon Cozens Tallest and Shortest (MIT) and Slobzheninov Highest & Lowest
Glyphs (Apache-2.0); see NOTICE. Modified to fix zero-as-unset and +/-9999 sentinel
bugs. First ordered layer wins ties; empty layers and repeated winners remain.
Native capture/tab access is separate and lazy, without a Glyphs dependency.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class LayerExtent:
    """One exact source glyph/layer and its unrounded vertical coordinates."""

    glyph: str
    layer: str
    bottom: float
    top: float


@dataclass(frozen=True)
class Extremes:
    """Both ordered winners; the same glyph/layer may occupy both positions."""

    highest: LayerExtent
    lowest: LayerExtent

    @property
    def layers(self) -> tuple[tuple[str, str], ...]:
        """Keep exact layer names and repeated occurrences for a fresh proof tab."""
        return tuple((row.glyph, row.layer) for row in (self.highest, self.lowest))


def choose(rows: Iterable[LayerExtent]) -> Extremes:
    """Scan the complete source before returning; never use numeric sentinels."""
    highest = lowest = None
    for row in rows:
        if (
            not isinstance(row, LayerExtent)
            or any(not isinstance(v, str) or not v for v in (row.glyph, row.layer))
            or any(
                type(v) not in (int, float) or not isfinite(v)
                for v in (row.bottom, row.top)
            )
            or row.bottom > row.top
        ):
            raise ValueError(
                "Every source layer needs names and finite ordered bounds."
            )
        if highest is None or row.top > highest.top:
            highest = row
        if lowest is None or row.bottom < lowest.bottom:
            lowest = row
    if highest is None:
        raise ValueError("The font has no eligible foreground layers.")
    return Extremes(highest, lowest)


def render(result: Extremes) -> str:
    """Keep source coordinate messages in an owned report, preserving Output."""
    high, low = result.highest, result.lowest
    return f"highest: {high.top}\nlowest: {low.bottom}\n\nHighest: {high.glyph} [{high.layer}]\nLowest: {low.glyph} [{low.layer}]"
