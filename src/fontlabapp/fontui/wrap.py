# this_file: src/fontlabapp/fontui/wrap.py
# SPDX-License-Identifier: Apache-2.0
"""Optional line wrapping for the sequence preview; display only, no layout.

Fontport places the run (advances and kerning); this only splits it into
lines no wider than width font units, restarting each line at x 0 (RTL lines
end at x 0). A glyph wider than width gets a line of its own.
"""

from math import isfinite
from typing import Any


def wrap(
    glyphs: list[Any], width: float | None, direction: str
) -> list[tuple[float, int]]:
    """Return a display (x, line) per occurrence, in run order."""
    if width is None or not isfinite(width) or width <= 0:
        return [(g.x, 0) for g in glyphs]
    result, line, edge = [], 0, None
    for g in glyphs:
        if direction == "ltr":
            if edge is not None and g.x - edge + g.advance > width:
                line, edge = line + 1, None
            edge = g.x if edge is None else edge
        else:
            if edge is not None and edge - g.x > width:
                line, edge = line + 1, None
            edge = g.x + g.advance if edge is None else edge
        result.append((g.x - edge, line))
    return result
