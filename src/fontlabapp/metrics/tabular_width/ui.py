# this_file: src/fontlabapp/metrics/tabular_width/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Show Check Tabular Widths through the shared owned snapshot panel."""

from typing import Any

import fontlabapp.metrics.tabular_width.model as api
from fontlabapp.proof.reports.snapshot_ui import SnapshotTextDialog


class TabularWidthDialog(SnapshotTextDialog):
    """Keep this report's source contract on the shared Refresh/Close lifecycle."""

    KEY = "check_tabular_widths"

    def __init__(self, parent: Any = None) -> None:
        """Build the complete report before showing the modeless panel."""
        super().__init__(
            parent,
            "Check Tabular Widths",
            self.KEY,
            "Compare actual selected Font/Glyph-window layers. The first occurrence is the reference; repeated editor slots retain their own layer choices. Metrics keys and Auto do not replace actual advances.",
            lambda: api.capture(),
            lambda report: api.render(report),
            lambda report: (
                f"Snapshot: {len(report.rows)} glyphs. Refresh after changes."
            ),
        )
