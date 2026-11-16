# this_file: src/fontlabapp/contours/svg_path/model.py
# SPDX-License-Identifier: Apache-2.0 AND MIT
"""Simon Cozens' complete own-path SVG command dump; see NOTICE.

The original emits Z and a blank line after EVERY contour, including open or
empty contours. Preserve that policy explicitly; this is not a complete SVG or
component exporter. Unsupported segments refuse the whole report.
"""

from math import isfinite
from typing import Any


def _point(point: tuple) -> str:
    """Keep numeric string precision; reject nonfinite/non-numeric operands."""
    if len(point) != 2 or any(
        type(v) not in (int, float) or not isfinite(v) for v in point
    ):
        raise ValueError("SVG operands must be finite numeric coordinates.")
    return f"{point[0]} {point[1]}"


def render(paths: tuple) -> str:
    """Return the original complete M/L/C/Z stream with no partial prefix."""
    result = []
    for path in paths:
        for index, segment in enumerate(path):
            if len(segment) not in (2, 4):
                raise ValueError(
                    "Only line or cubic segments are supported; no partial report."
                )
            points = tuple(_point(point) for point in segment)
            if index == 0:
                result.append(f"M {points[0]}\n")
            command = "L" if len(segment) == 2 else "C"
            result.append(f"{command} {' '.join(points[1:])}\n")
        result.append("Z\n\n")
    return "".join(result)


def show() -> Any:
    """Open the shared owned Refresh/Close report through Fly/App dispatch."""
    from fontlabapp.proof.reports.specialized_ui import SvgPathCommandsDialog
    from fontlabapp.core.scripting import show_script_dialog

    return show_script_dialog(SvgPathCommandsDialog, SvgPathCommandsDialog.KEY)
