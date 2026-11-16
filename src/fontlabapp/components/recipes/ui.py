# this_file: src/fontlabapp/components/recipes/ui.py
# SPDX-License-Identifier: Apache-2.0 AND MIT
"""Show Dump Component Recipes through the shared owned snapshot panel."""

from typing import Any

import fontlabapp.components.recipes.model as api
from fontlabapp.proof.reports.snapshot_ui import SnapshotTextDialog


class ComponentRecipesDialog(SnapshotTextDialog):
    """Keep this report's source contract on the shared Refresh/Close lifecycle."""

    KEY = "component_recipes"

    def __init__(self, parent: Any = None) -> None:
        """Build the complete report before showing the modeless panel."""
        super().__init__(
            parent,
            "Dump Component Recipes",
            self.KEY,
            "Selected Font/Glyph-window layers, including repeated editor occurrences and their layer choices. Recipes retain component order; positions and transforms are not encoded.",
            lambda: api.capture(),
            lambda report: api.recipes(report.layers),
            lambda report: (
                f"Recipes: {sum(bool(layer.components) for layer in report.layers)} · Layers: {len(report.layers)} · Current master: {report.master}. Refresh after changes."
            ),
        )
