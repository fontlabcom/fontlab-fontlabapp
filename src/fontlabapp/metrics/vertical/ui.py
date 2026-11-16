# this_file: src/fontlabapp/metrics/vertical/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Show the all-master stored-metrics report in an owned snapshot panel."""

from typing import Any

import fontlabapp.metrics.vertical.native as api
from fontlabapp.proof.reports.snapshot_ui import SnapshotTextDialog


class VerticalMetricsDialog(SnapshotTextDialog):
    """Share Refresh/Close cleanup without touching the native Output panel."""

    KEY = "vertical_metrics_reporter"

    def __init__(self, parent: Any = None) -> None:
        """Capture every open font/master before presenting the report."""
        super().__init__(
            parent,
            "Vertical Metrics Reporter",
            self.KEY,
            "Compare eight stored metric values across every master in every open font. Unset hhea values remain None. Exported or automatically derived values are outside this report.",
            lambda: api.capture(),
            lambda report: api.render(report),
            lambda report: (
                f"Snapshot: {report.fonts} fonts, {len(report.rows)} masters. Refresh after changes."
            ),
        )
