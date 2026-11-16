# this_file: src/fontlabapp/contours/near_miss/ui.py
# SPDX-License-Identifier: MIT AND Apache-2.0
"""Own the complete Simon Cozens near-miss report in the existing shared shell."""

from typing import Any

import fontlabapp.contours.near_miss.model as report
import fontlabapp.contours.near_miss.native as native
from fontlabapp.proof.reports.snapshot_ui import SnapshotTextDialog


class NearMissDialog(SnapshotTextDialog):
    """Modeless selectable report with atomic Refresh and owned Close cleanup."""

    KEY = "near_miss"

    def __init__(self, parent: Any = None) -> None:
        super().__init__(
            parent,
            "Close But No Cigar",
            self.KEY,
            "All selected glyph occurrences, each first layer and associated master. Strict near-angle, horizontal/vertical stem-length and all-node position checks. Original open-path closing edge and curve-length sampling retained; numeric cubic angle repaired. Refresh replaces the complete report.",
            native.capture,
            report.render,
            lambda rows: f"{len(rows)} selected glyph occurrences. No font changes.",
        )
