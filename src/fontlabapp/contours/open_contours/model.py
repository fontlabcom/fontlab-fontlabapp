# this_file: src/fontlabapp/contours/open_contours/model.py
# SPDX-License-Identifier: Apache-2.0
"""Open Contours: pure scan and text rendering over a font and a package.

``scan`` reads every glyph of the font on every master layer and lists each
open contour with its node count and the distance between its end nodes.
Nothing is written.
"""

from dataclasses import dataclass
from math import hypot
from typing import Any

HEADER = "Glyph\tMaster\tContour\tNodes\tEnd gap"


@dataclass(frozen=True)
class OpenContoursReport:
    """One scan: the package it was read from, master count and rows."""

    package_id: int
    masters: int
    rows: tuple


def scan(font: Any, package: Any) -> tuple:
    """Rows ``(glyph, master, contour index, node count, end gap)`` of open contours."""
    rows = []
    for source in font.glyphs:
        glyph = package.findName(source.name)
        if glyph is None:
            continue
        for master in package.masters:
            layer = glyph.findLayer(master)
            if layer is None:
                continue
            for index, contour in enumerate(layer.getContours()):
                if contour.closed:
                    continue
                nodes = contour.nodes()
                gap = hypot(nodes[-1].x - nodes[0].x, nodes[-1].y - nodes[0].y) if len(nodes) > 1 else 0.0
                rows.append((source.name, master, index, len(nodes), round(gap, 1)))
    return tuple(rows)


def render(report: OpenContoursReport) -> str:
    """Tab-separated table, contour numbers one-based."""
    lines = [HEADER]
    lines += [f"{g}\t{m}\t#{i + 1}\t{n}\t{gap}" for g, m, i, n, gap in report.rows]
    return "\n".join(lines)


def summary(report: OpenContoursReport) -> str:
    """One-line result for the status bar."""
    if not report.rows:
        return f"No open contours on any of {report.masters} masters."
    glyphs = len({row[0] for row in report.rows})
    count = len(report.rows)
    return (f"{count} open contour{'s' if count != 1 else ''} in {glyphs} glyph{'s' if glyphs != 1 else ''}"
            f" across {report.masters} masters.")
