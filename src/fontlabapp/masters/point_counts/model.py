# this_file: src/fontlabapp/masters/point_counts/model.py
# SPDX-License-Identifier: Apache-2.0
"""Independent Reza Point Counter report, restricted to every selected master's rows.

The inspected original has no declared licence; no original body is copied.
Quadratic endpoints count as curves, explicitly correcting its omitted points.
"""

from typing import Any

from fontlabapp.contours.point_counts.model import LayerCount

KEY = "master-point-counter"


def render(rows: tuple[LayerCount, ...]) -> str:
    """Keep original row text, order, duplicates, blank separators and final newline."""
    blocks = []
    for row in rows:
        count = row.counts
        blocks.append(
            f"Layer: {row.name}\nTotal: {count.points} Points - "
            f"{count.handles} Handles, {count.lines + count.curves} Nodes, "
            f"{count.paths} Paths\n"
        )
    return "\n".join(blocks)


def show() -> Any:
    """Open the complete master-only snapshot through the owned script registry."""
    from fontlabapp.masters.point_counts.ui import dialog_type
    from fontlabapp.core.scripting import show_script_dialog

    return show_script_dialog(dialog_type(), KEY)
