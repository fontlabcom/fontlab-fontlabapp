# this_file: src/fontlabapp/guides/perpendicular/model.py
# SPDX-License-Identifier: Apache-2.0
"""Selection-driven guides, independently adapted from Reset Type Studio.

Keep the original nearest-two-distinct-node rule, not a Bezier derivative.
Input node order resolves distance ties; coincident distinct nodes remain valid.
Component rectangles are actual native transformed ink bounds. See NOTICE.
"""

from math import atan2, isfinite, pi
from typing import Any

TITLE = "Perpendicular Guides"
Point = tuple[int, float, float]
Bounds = tuple[int, float, float, float, float]
Guide = tuple[float, float, float]


def plan(nodes: tuple[Point, ...], components: tuple[Bounds, ...]) -> tuple:
    """Return ordered (x,y,radians) additions and original diagnostic messages."""
    if any(not isfinite(v) for row in (*nodes, *components) for v in row[1:]):
        raise ValueError("Selected coordinates and bounds must be finite.")
    if len({n[0] for n in nodes}) != len(nodes):
        raise ValueError("Selected node identities must be distinct.")
    rows, messages = [], []
    if len(nodes) >= 2:
        x = sum(n[1] for n in nodes) / len(nodes)
        y = sum(n[2] for n in nodes) / len(nodes)
        pair = (
            nodes
            if len(nodes) == 2
            else sorted(nodes, key=lambda n: (n[1] - x) ** 2 + (n[2] - y) ** 2)[:2]
        )
        a, b = pair
        rows.append((x, y, atan2(b[2] - a[2], b[1] - a[1]) + pi / 2))
    elif nodes:
        messages.append("Please select at least two points.")
    for _, x, y, width, height in components:
        rows.extend(
            (
                (x + width / 2, y + height / 2, 0),
                (x + width / 2, y + height / 2, pi / 2),
            )
        )
    if not nodes and not components:
        messages.append("Please select path nodes or components.")
    return tuple(rows), tuple(messages)


def run() -> dict[str, Any]:
    """Add the complete first-selected-layer plan with one native history step."""
    from fontlabapp.guides.perpendicular.native import execute

    return execute()
