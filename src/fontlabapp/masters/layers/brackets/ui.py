# this_file: src/fontlabapp/masters/layers/brackets/ui.py
# SPDX-License-Identifier: Apache-2.0
"""Own the full-font bracket-layer report without clearing the owner's Output."""

from typing import Any

import fontlabapp.masters.layers.brackets.native as native
import fontlabapp.masters.layers.brackets.model as api
from fontlabapp.proof.reports.snapshot_ui import SnapshotTextDialog


class BracketLayersDialog(SnapshotTextDialog):
    """Retain complete read-only groups and shared Refresh/Close cleanup."""

    KEY = "bracket_layers"

    def __init__(self, parent: Any = None) -> None:
        super().__init__(
            parent,
            "Bracket Layer Report",
            self.KEY,
            "Scan the current font for layer names containing both [ and ], plus glyphs that depend on them through components.",
            lambda: native.report(),
            lambda result: api.render(result),
            lambda result: (
                f"Scanned glyphs: {result.glyph_count}. Distinct affected glyphs: {result.total}. Refresh after changes."
            ),
        )
        self.resize(500, 400)
        self.setMinimumSize(500, 400)
