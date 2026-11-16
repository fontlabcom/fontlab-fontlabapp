# this_file: src/fontlabapp/contours/point_counts/model.py
# SPDX-License-Identifier: Apache-2.0
"""Immutable Point Counter reports, adapted from Slobzheninov (see NOTICE).

Keep selected occurrence groups and the original two-previous-row marker.
Quadratic on-curves count as curves, correcting the original omitted points.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Counts:
    """Own contour nodes only; components are never decomposed."""

    lines: int
    curves: int
    handles: int
    paths: int

    @property
    def points(self) -> int:
        """Include every on-curve and control, including quadratic nodes."""
        return self.lines + self.curves + self.handles


@dataclass(frozen=True)
class LayerCount:
    """One foreground layer in native stored order, including empty layers."""

    name: str
    counts: Counts


@dataclass(frozen=True)
class GlyphCount:
    """One selected occurrence; repeated glyph groups remain repeated."""

    name: str
    layers: tuple[LayerCount, ...]


def render(groups: tuple[GlyphCount, ...]) -> str:
    """Preserve source report text and marker against the previous two rows."""
    result = []
    for group in groups:
        result.append(f"---------- {group.name} ----------\n")
        previous = ()
        for layer in group.layers:
            count = layer.counts
            marker = "? " if previous and count.points not in previous else ""
            result.append(
                f"{marker}{count.points} points - {count.lines} lines, "
                f"{count.curves} curves, {count.handles} offcurves, "
                f"{count.paths} paths - {layer.name}\n"
            )
            previous = (*previous[-1:], count.points)
        result.append("\n")
    return "".join(result)
