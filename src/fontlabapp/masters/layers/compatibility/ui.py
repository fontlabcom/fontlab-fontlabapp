# this_file: src/fontlabapp/masters/layers/compatibility/ui.py
# SPDX-License-Identifier: MIT
"""Own the complete Why You Not Compatible? report and Refresh/Close lifecycle."""

from typing import Any

import fontlabapp.masters.layers.compatibility.model as api
import fontlabapp.masters.layers.compatibility.native as native
from fontlabapp.proof.reports.snapshot_ui import SnapshotTextDialog


class LayerCompatibilityDialog(SnapshotTextDialog):
    """Report original structural checks without clearing owner Output."""

    KEY = "layer_compatibility"

    def __init__(self, parent: Any = None) -> None:
        super().__init__(
            parent,
            "Why You Not Compatible?",
            self.KEY,
            "Compare adjacent foreground layers for every selected occurrence: path/node counts and types, anchor-name sets and component-name sets. These source checks are not an export-compatibility certificate.",
            lambda: native.capture(),
            lambda report: api.render(report),
            lambda report: (
                f"Snapshot: {len(report)} selected occurrences. Refresh after changes."
            ),
        )
