# this_file: src/fontlabapp/contours/point_counts/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Show Point Counter through the shared owned snapshot panel."""

from typing import Any

import fontlabapp.contours.point_counts.native as api
from fontlabapp.proof.reports.snapshot_ui import SnapshotTextDialog


class PointCountsDialog(SnapshotTextDialog):
    """Keep this report's source contract on the shared Refresh/Close lifecycle."""

    KEY = "point_counter"

    def __init__(self, parent: Any = None) -> None:
        """Build the complete report before showing the modeless panel."""
        super().__init__(
            parent,
            "Point Counter",
            self.KEY,
            "Count own contour nodes in every foreground layer of each selected glyph occurrence. Quadratic on-curves count as curves. Components are not decomposed.",
            lambda: api.capture(),
            lambda report: api.render(report),
            lambda report: (
                f"Snapshot: {len(report)} selected occurrences. Refresh after changes."
            ),
        )
